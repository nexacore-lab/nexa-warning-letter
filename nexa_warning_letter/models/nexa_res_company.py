from odoo import _, api, fields, models

# One numbering (ir.sequence) per company; the prefix can be changed from the settings.
SEQUENCE_CODE = 'nex.warning.letter'
SEQUENCE_PREFIX = 'WL/%(year)s/'


class ResCompany(models.Model):
    _inherit = 'res.company'

    nex_warning_notify_email = fields.Boolean(
        string='E-mail Warning Letters to Employees', default=True,
        help='When a warning letter is issued, the employee receives it by e-mail.')
    nex_warning_cc_watchers = fields.Boolean(
        string='Copy the Watchers', default=True,
        help='The watchers of a warning letter receive a copy of the e-mail sent to the employee.')

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._nex_warning_init()
        return companies

    def _nex_warning_default_types(self):
        """Default warning letter types, named in the language of the company."""
        self.ensure_one()
        env = self.with_context(lang=self.partner_id.lang or self.env.lang or 'en_US').env
        return [
            (1, env._('Documented Verbal Warning'), 3),
            (2, env._('Warning Letter 1'), 6),
            (3, env._('Warning Letter 2'), 6),
            (4, env._('Warning Letter 3'), 6),
        ]

    def _nex_warning_init(self):
        """Numbering and default types of each company (can be run again)."""
        self._nex_warning_ensure_sequence()
        Type = self.env['nex.warning.letter.type'].sudo().with_context(active_test=False)
        for company in self:
            if Type.search_count([('company_id', '=', company.id)], limit=1):
                continue
            Type.create([{
                'name': name,
                'sequence': sequence,
                'validity_months': months,
                'company_id': company.id,
            } for sequence, name, months in company._nex_warning_default_types()])
        return True

    def _nex_warning_ensure_sequence(self):
        Sequence = self.env['ir.sequence'].sudo().with_context(active_test=False)
        for company in self:
            if Sequence.search_count([('code', '=', SEQUENCE_CODE), ('company_id', '=', company.id)], limit=1):
                continue
            Sequence.create({
                'name': self.with_context(lang=company.partner_id.lang or self.env.lang).env._('Warning Letter'),
                'code': SEQUENCE_CODE,
                'prefix': SEQUENCE_PREFIX,
                'padding': 4,
                # official numbers: no gap left by a rolled back transaction
                'implementation': 'no_gap',
                'company_id': company.id,
            })
        return True

    def _nex_warning_next_number(self):
        self.ensure_one()
        Sequence = self.env['ir.sequence'].sudo().with_company(self)
        number = Sequence.next_by_code(SEQUENCE_CODE)
        if not number:
            self._nex_warning_ensure_sequence()
            number = Sequence.next_by_code(SEQUENCE_CODE)
        return number


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    nex_warning_notify_email = fields.Boolean(
        related='company_id.nex_warning_notify_email', readonly=False)
    nex_warning_cc_watchers = fields.Boolean(
        related='company_id.nex_warning_cc_watchers', readonly=False)

    def action_nex_warning_numbering(self):
        """Numbering of the warning letters of the current company."""
        self.ensure_one()
        company = self.company_id or self.env.company
        company._nex_warning_ensure_sequence()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Warning Letter Numbering'),
            'res_model': 'ir.sequence',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('company_id', '=', company.id), ('code', '=', SEQUENCE_CODE)],
            'context': {'default_company_id': company.id, 'default_code': SEQUENCE_CODE,
                        'active_test': False},
        }
