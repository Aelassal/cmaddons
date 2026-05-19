import base64
import io
import json
import logging
import zipfile

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models import matcher

_logger = logging.getLogger(__name__)


class BulkMediaWizard(models.TransientModel):
    _name = "bulk.media.wizard"
    _description = "Bulk Product Media Upload Wizard"

    name = fields.Char(default="Bulk Media Upload", readonly=True)
    upload_archive = fields.Binary(
        string="Image archive (.zip)",
        required=True,
        help="Upload a ZIP file containing product images. "
             "Filenames should start with the product's internal reference or barcode.",
    )
    archive_filename = fields.Char()

    fuzzy_threshold = fields.Float(
        default=0.85,
        help="0.0–1.0. Lower values accept looser filename matches. "
             "0.85 is a safe default; 1.0 = exact match only.",
    )
    apply_to_variants = fields.Boolean(
        default=True,
        help="If a filename includes attribute values after the SKU "
             "(e.g. SKU123-red-L.jpg), upload to the matching variant instead of the template.",
    )

    state = fields.Selection(
        [("upload", "Upload"), ("preview", "Preview"), ("done", "Done")],
        default="upload",
        readonly=True,
    )

    preview_json = fields.Text(readonly=True)
    result_summary = fields.Text(readonly=True)

    def action_preview(self):
        self.ensure_one()
        plan = self._build_plan()
        self.write({
            "state": "preview",
            "preview_json": json.dumps(plan, indent=2, default=str),
        })
        return self._reopen()

    def action_apply(self):
        self.ensure_one()
        plan = self._build_plan()
        matched = plan["matched"]
        unmatched = plan["unmatched"]

        archive = self._open_archive()
        try:
            for entry in matched:
                self._apply_one(archive, entry)
        finally:
            archive.close()

        summary = _(
            "Applied %(n)s images.\n"
            "Unmatched files: %(u)s\n"
            "See the preview pane for details."
        ) % {"n": len(matched), "u": len(unmatched)}
        self.write({"state": "done", "result_summary": summary})
        return self._reopen()

    def action_reset(self):
        self.ensure_one()
        self.write({"state": "upload", "preview_json": False, "result_summary": False})
        return self._reopen()

    # --- internals -----------------------------------------------------

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _open_archive(self):
        if not self.upload_archive:
            raise UserError(_("Please upload a ZIP file first."))
        data = base64.b64decode(self.upload_archive)
        try:
            return zipfile.ZipFile(io.BytesIO(data), "r")
        except zipfile.BadZipFile:
            raise UserError(_("The uploaded file is not a valid ZIP archive."))

    def _index_products(self):
        Template = self.env["product.template"].sudo()
        templates = Template.search([])
        by_ref = {}
        by_barcode = {}
        all_list = []
        for t in templates:
            all_list.append((t.id, t.default_code or "", t.name or ""))
            if t.default_code:
                by_ref[matcher.normalize(t.default_code)] = t.id
            # Only templates with a single variant have a meaningful barcode at template level.
            if t.product_variant_count == 1 and t.barcode:
                by_barcode[matcher.normalize(t.barcode)] = t.id
        return by_ref, by_barcode, all_list

    def _build_plan(self):
        archive = self._open_archive()
        try:
            by_ref, by_barcode, all_list = self._index_products()
            matched = []
            unmatched = []
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if not matcher.is_image(info.filename):
                    continue
                parsed = matcher.parse_filename(info.filename)
                hit = matcher.find_product(
                    parsed, by_ref, by_barcode, all_list,
                    fuzzy_threshold=self.fuzzy_threshold,
                )
                if hit:
                    matched.append({
                        "file": info.filename,
                        "template_id": hit["template_id"],
                        "match_by": hit["match_by"],
                        "score": round(hit["score"], 3),
                        "modifiers": hit["modifiers"],
                        "position": parsed["position"],
                        "is_thumb": parsed["is_thumb"],
                    })
                else:
                    unmatched.append({"file": info.filename})
            # Enrich matched with template names for preview readability
            if matched:
                templates = self.env["product.template"].browse(
                    list({m["template_id"] for m in matched})
                )
                names = {t.id: t.display_name for t in templates}
                for m in matched:
                    m["template_name"] = names.get(m["template_id"], "")
            return {"matched": matched, "unmatched": unmatched}
        finally:
            archive.close()

    def _apply_one(self, archive, entry):
        Template = self.env["product.template"]

        tmpl = Template.browse(entry["template_id"])
        with archive.open(entry["file"]) as fh:
            img_bytes = fh.read()
        img_b64 = base64.b64encode(img_bytes)

        target = tmpl
        if self.apply_to_variants and entry["modifiers"]:
            variant = self._resolve_variant(tmpl, entry["modifiers"])
            if variant:
                target = variant

        if entry["is_thumb"]:
            target.write({"image_128": img_b64})
            return

        if entry["position"] in (None, 1):
            target.write({"image_1920": img_b64})
            return

        # Gallery position → product.image record (requires website_sale)
        if "product.image" in self.env.registry.models:
            self.env["product.image"].create({
                "name": entry["file"],
                "image_1920": img_b64,
                "product_tmpl_id": tmpl.id,
                "sequence": entry["position"] or 10,
            })
        else:
            _logger.info(
                "cm_sa_bulk_product_media_drop: %s has gallery position %s but "
                "product.image model is not registered (install website_sale "
                "to enable gallery slots); skipping.",
                entry["file"], entry["position"],
            )

    def _resolve_variant(self, template, modifier_tokens):
        """Given ['red', 'L'], return the matching product.product or False."""
        if not modifier_tokens or not template.product_variant_ids:
            return False
        want = {matcher.normalize(m) for m in modifier_tokens}
        best_score = 0
        best_variant = False
        for variant in template.product_variant_ids:
            values = {matcher.normalize(name) for name in variant.product_template_attribute_value_ids.mapped("name")}
            overlap = len(want & values)
            if overlap > best_score:
                best_score = overlap
                best_variant = variant
        return best_variant if best_score >= 1 else False
