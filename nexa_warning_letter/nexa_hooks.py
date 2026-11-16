from .models.nexa_res_company import SEQUENCE_CODE


def post_init_hook(env):
    """Numbering and default warning letter types of every company."""
    env['res.company'].sudo().with_context(active_test=False).search([])._nex_warning_init()


def uninstall_hook(env):
    env['ir.sequence'].sudo().with_context(active_test=False).search(
        [('code', '=', SEQUENCE_CODE)]).unlink()
