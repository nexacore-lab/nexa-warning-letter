from odoo import _, fields, models

from .nexa_warning_letter import OFFICER_GROUP


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    nex_warning_letter_ids = fields.One2many(
        'nex.warning.letter', 'employee_id', string='Warning Letters', groups=OFFICER_GROUP)
    nex_warning_letter_count = fields.Integer(
        string='Warning Letter Count', compute='_compute_nex_warning_letter_count', groups=OFFICER_GROUP)
    nex_active_warning_count = fields.Integer(
        string='Active Warning Letters', compute='_compute_nex_warning_letter_count', groups=OFFICER_GROUP,
        help='Issued warning letters of the employee that are valid today.')

    def _compute_nex_warning_letter_count(self):
        Letter = self.env['nex.warning.letter']
        saved = self._origin
        counts = dict(Letter._read_group(
            [('employee_id', 'in', saved.ids)], ['employee_id'], ['__count'])) if saved else {}
        active = dict(Letter._read_group(
            [('employee_id', 'in', saved.ids), ('state', '=', 'issued'), ('validity_status', '=', 'active')],
            ['employee_id'], ['__count'])) if saved else {}
        for employee in self:
            employee.nex_warning_letter_count = counts.get(employee._origin, 0)
            employee.nex_active_warning_count = active.get(employee._origin, 0)

    def action_nex_view_warning_letters(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Warning Letters'),
            'res_model': 'nex.warning.letter',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
