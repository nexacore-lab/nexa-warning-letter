from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class NexWarningLetterType(models.Model):
    _name = 'nex.warning.letter.type'
    _description = 'Warning Letter Type'
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description', translate=True)
    color = fields.Integer(string='Color')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    validity_months = fields.Integer(
        string='Default Validity (Months)', default=6,
        help='Fills the end date of a new warning letter of this type. 0: the end date is entered by hand.')

    @api.constrains('validity_months')
    def _check_validity_months(self):
        for rec in self:
            if not 0 <= rec.validity_months <= 60:
                raise ValidationError(_('The default validity must be between 0 and 60 months.'))

    @api.constrains('name', 'company_id')
    def _check_unique_name(self):
        for rec in self:
            if self.with_context(active_test=False).search_count([
                ('id', '!=', rec.id), ('name', '=', rec.name), ('company_id', '=', rec.company_id.id),
            ], limit=1):
                raise ValidationError(_('A warning letter type named %s already exists in this company.',
                                        rec.name))
