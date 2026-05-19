import json
import logging
import os
import time

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MIN_AGE_SECONDS = 24 * 60 * 60  # 24h safety rail


class CmSaFilestoreSweepWizard(models.TransientModel):
    _name = "cm_sa.filestore.sweep.wizard"
    _description = "Filestore Sweep Wizard"

    scan_started = fields.Datetime(readonly=True)
    orphan_count = fields.Integer(readonly=True)
    orphan_size_mb = fields.Float(readonly=True, digits=(12, 3))
    orphan_preview = fields.Text(readonly=True)
    action_state = fields.Selection(
        [("idle", "Idle"), ("scanned", "Scanned"), ("applied", "Applied")],
        default="idle",
        readonly=True,
    )
    last_run_id = fields.Many2one(
        "cm_sa.filestore.sweep.run",
        readonly=True,
    )
    # internal: JSON list of relative paths found orphan, kept across
    # re-opens of the same wizard row.
    orphans_blob = fields.Text()

    # ------------------------------------------------------------------
    # Filestore walking
    # ------------------------------------------------------------------
    @api.model
    def _filestore_dir(self):
        return tools.config.filestore(self.env.cr.dbname)

    @api.model
    def _iter_filestore(self):
        """Yield (relative_path, absolute_path, size, mtime) for every
        file in the current DB's filestore."""
        root = self._filestore_dir()
        if not root or not os.path.isdir(root):
            return
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                absf = os.path.join(dirpath, fname)
                try:
                    st = os.stat(absf)
                except OSError:
                    continue
                relf = os.path.relpath(absf, root)
                # Normalize to forward slashes to match store_fname style
                relf = relf.replace(os.sep, "/")
                yield relf, absf, st.st_size, st.st_mtime

    def _known_store_fnames(self):
        """Return set of store_fname values currently used by ir.attachment."""
        self.env.cr.execute(
            "SELECT store_fname FROM ir_attachment WHERE store_fname IS NOT NULL"
        )
        return {row[0] for row in self.env.cr.fetchall() if row[0]}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_scan(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only Administrators can run the filestore sweeper."))

        known = self._known_store_fnames()
        now = time.time()
        orphans = []
        total_bytes = 0
        total_scanned = 0
        for relf, _absf, size, mtime in self._iter_filestore():
            total_scanned += 1
            if relf in known:
                continue
            if now - mtime < MIN_AGE_SECONDS:
                continue
            orphans.append({"path": relf, "size": size})
            total_bytes += size

        preview = orphans[:50]
        self.write({
            "scan_started": fields.Datetime.now(),
            "orphan_count": len(orphans),
            "orphan_size_mb": round(total_bytes / (1024 * 1024), 3),
            "orphan_preview": json.dumps(preview, indent=2),
            "orphans_blob": json.dumps(orphans),
            "action_state": "scanned",
        })
        # Write a dry-run log row for traceability
        run = self.env["cm_sa.filestore.sweep.run"].create({
            "started_at": self.scan_started,
            "completed_at": fields.Datetime.now(),
            "total_scanned": total_scanned,
            "orphan_count": len(orphans),
            "orphan_size_mb": self.orphan_size_mb,
            "deleted_count": 0,
            "deleted_size_mb": 0.0,
            "triggered_by": self.env.user.id,
            "dry_run": True,
            "notes": _("Scan only — no deletion performed."),
        })
        self.last_run_id = run.id
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_delete(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only Administrators can delete orphans."))
        if self.action_state != "scanned":
            raise UserError(_("Run a scan first."))

        try:
            orphans = json.loads(self.orphans_blob or "[]")
        except Exception:
            orphans = []
        if not orphans:
            raise UserError(_("Nothing to delete. Re-scan first."))

        root = self._filestore_dir()
        now = time.time()
        deleted = 0
        deleted_bytes = 0
        errors = []
        for entry in orphans:
            rel = entry.get("path")
            if not rel:
                continue
            absf = os.path.join(root, rel.replace("/", os.sep))
            if not os.path.isfile(absf):
                continue
            try:
                st = os.stat(absf)
                if now - st.st_mtime < MIN_AGE_SECONDS:
                    continue
                size = st.st_size
                os.remove(absf)
                deleted += 1
                deleted_bytes += size
            except OSError as exc:
                errors.append("%s: %s" % (rel, exc))
                _logger.warning("filestore_sweeper: %s removal failed: %s", absf, exc)

        run = self.env["cm_sa.filestore.sweep.run"].create({
            "started_at": fields.Datetime.now(),
            "completed_at": fields.Datetime.now(),
            "total_scanned": len(orphans),
            "orphan_count": len(orphans),
            "orphan_size_mb": self.orphan_size_mb,
            "deleted_count": deleted,
            "deleted_size_mb": round(deleted_bytes / (1024 * 1024), 3),
            "triggered_by": self.env.user.id,
            "dry_run": False,
            "notes": "\n".join(errors) if errors else False,
        })
        self.write({
            "action_state": "applied",
            "last_run_id": run.id,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Filestore sweep complete"),
                "message": _(
                    "Deleted %(n)s orphan file(s), freed %(mb).2f MB."
                ) % {"n": deleted, "mb": round(deleted_bytes / (1024 * 1024), 2)},
                "type": "success",
                "sticky": False,
            },
        }
