from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

OFFICER_GROUP = 'hr.group_hr_user'
# Context value of the workflow methods: a module level object cannot be sent
# through RPC, so only these methods write the workflow fields.
_FLOW_TOKEN = object()
FLOW_CONTEXT_KEY = 'nex_warning_flow'
FLOW_FIELDS = frozenset({'state', 'name', 'issued_on', 'acknowledged_on'})
# Content of the letter, frozen once it is issued or cancelled
LOCKED_FIELDS = frozenset({
    'employee_id', 'company_id', 'type_id', 'effective_date', 'end_date', 'notes',
})


class NexWarningLetter(models.Model):
    """Warning letter given to an employee."""

    _name = 'nex.warning.letter'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Warning Letter'
    _order = 'effective_date desc, id desc'
    _check_company_auto = True
    _rec_names_search = ['name', 'employee_name']
    # The employee and the watchers reply in the chatter of a letter they can read
    _mail_post_access = 'read'

    name = fields.Char(string='Number', readonly=True, copy=False, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, tracking=True, index=True,
        ondelete='restrict', check_company=True)
    employee_name = fields.Char(string='Employee Name', related='employee_id.name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True, readonly=True,
        compute='_compute_company_id', store=True, precompute=True)
    department_id = fields.Many2one(
        'hr.department', string='Department', related='employee_id.department_id', store=True)
    job_title = fields.Char(string='Job Position', related='employee_id.job_title', store=True)
    type_id = fields.Many2one(
        'nex.warning.letter.type', string='Type', required=True, tracking=True,
        ondelete='restrict', check_company=True)
    effective_date = fields.Date(
        string='Effective Date', required=True, tracking=True, default=fields.Date.context_today)
    end_date = fields.Date(
        string='End Date', required=True, tracking=True,
        compute='_compute_end_date', store=True, readonly=False, precompute=True)
    notes = fields.Text(string='Details', help='Facts and reasons, sent to the employee and to the watchers.')
    internal_note = fields.Text(
        string='Internal Note', groups=OFFICER_GROUP,
        help='Only HR can read this note: it is never sent to the employee or to the watchers.')
    watcher_ids = fields.Many2many(
        'hr.employee', 'nex_warning_letter_watcher_rel', 'letter_id', 'employee_id',
        string='Watchers', check_company=True,
        help='Employees (for example the manager) who receive a copy of the warning letter, '
             'follow its comments and can read it.')
    watcher_names = fields.Char(string='Watched By', compute='_compute_watcher_names', compute_sudo=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'nex_warning_letter_attachment_rel', 'letter_id', 'attachment_id',
        string='Attachments')
    state = fields.Selection(
        [('draft', 'Draft'), ('issued', 'Issued'), ('cancelled', 'Cancelled')],
        string='Status', required=True, default='draft', tracking=True, copy=False)
    issued_on = fields.Datetime(
        string='Issued On', readonly=True, copy=False,
        help='When the warning letter was issued for the first time.')
    acknowledged_on = fields.Datetime(
        string='Read by the Employee On', readonly=True, copy=False, tracking=True,
        help='When the employee confirmed having read the warning letter.')
    validity_status = fields.Selection(
        [('upcoming', 'Upcoming'), ('active', 'Active'), ('expired', 'Expired')],
        string='Validity', compute='_compute_validity_status', search='_search_validity_status')
    can_acknowledge = fields.Boolean(compute='_compute_can_acknowledge')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends('name', 'employee_name')
    def _compute_display_name(self):
        for rec in self:
            number = rec.name or _('Draft')
            rec.display_name = f'{number} - {rec.employee_name}' if rec.employee_name else number

    @api.depends('employee_id')
    def _compute_company_id(self):
        # The letter belongs to the company of the employee when it is drafted
        for rec in self:
            if rec.state in (False, 'draft') and rec.employee_id:
                rec.company_id = rec.employee_id.company_id
            elif not rec.company_id:
                rec.company_id = rec.employee_id.company_id or self.env.company

    @api.depends('type_id.validity_months', 'effective_date')
    def _compute_end_date(self):
        for rec in self:
            if rec.state not in (False, 'draft'):
                continue
            months = rec.type_id.validity_months
            if months > 0 and rec.effective_date:
                rec.end_date = rec.effective_date + relativedelta(months=months) - timedelta(days=1)

    @api.depends('watcher_ids')
    def _compute_watcher_names(self):
        for rec in self:
            rec.watcher_names = ', '.join(rec.watcher_ids.mapped('name'))

    @api.depends('effective_date', 'end_date')
    def _compute_validity_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.effective_date and rec.effective_date > today:
                rec.validity_status = 'upcoming'
            elif rec.end_date and rec.end_date < today:
                rec.validity_status = 'expired'
            else:
                rec.validity_status = 'active'

    def _search_validity_status(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise UserError(_('This search on the validity is not supported: %s', operator))
        values = [value] if operator in ('=', '!=') else list(value or [])
        today = fields.Date.context_today(self)
        domains = {
            'upcoming': [('effective_date', '>', today)],
            'active': ['&', ('effective_date', '<=', today), ('end_date', '>=', today)],
            'expired': [('end_date', '<', today)],
        }
        parts = [domains[v] for v in values if v in domains]
        if not parts:
            domain = [('id', '=', False)]
        else:
            domain = ['|'] * (len(parts) - 1) + [term for part in parts for term in part]
        if operator in ('!=', 'not in'):
            # the domain above is one expression in prefix notation
            domain = ['!'] + domain
        return domain

    @api.depends_context('uid')
    @api.depends('state', 'acknowledged_on', 'employee_id')
    def _compute_can_acknowledge(self):
        user = self.env.user
        for rec in self:
            rec.can_acknowledge = (
                rec.state == 'issued' and not rec.acknowledged_on
                and rec.sudo().employee_id.user_id == user)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('effective_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.effective_date and rec.end_date and rec.end_date < rec.effective_date:
                raise ValidationError(_('The end date cannot be earlier than the effective date.'))

    @api.constrains('employee_id', 'watcher_ids')
    def _check_watchers(self):
        for rec in self:
            if rec.employee_id in rec.watcher_ids:
                raise ValidationError(_('The employee cannot watch his own warning letter.'))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _nex_in_flow(self):
        return self.env.context.get(FLOW_CONTEXT_KEY) is _FLOW_TOKEN

    @api.model_create_multi
    def create(self, vals_list):
        in_flow = self._nex_in_flow()
        Employee = self.env['hr.employee'].sudo()
        Type = self.env['nex.warning.letter.type'].sudo()
        for vals in vals_list:
            if not in_flow and (FLOW_FIELDS & {k for k, v in vals.items() if v and k != 'state'}
                                or (vals.get('state') or 'draft') != 'draft'):
                raise UserError(_('A warning letter is created as a draft. It gets its number when it is issued.'))
            employee = Employee.browse(vals.get('employee_id'))
            if employee and vals.get('company_id') and vals['company_id'] != employee.company_id.id:
                raise ValidationError(_('The company of a warning letter must be the company of its employee.'))
            if not vals.get('end_date') and vals.get('type_id') \
                    and Type.browse(vals['type_id']).validity_months <= 0:
                raise ValidationError(_('Enter the end date: this type of warning letter has no default validity.'))
        records = super().create(vals_list)
        if any(vals.get('attachment_ids') for vals in vals_list):
            records._nex_link_attachments()
        return records

    def write(self, vals):
        if not self._nex_in_flow():
            if FLOW_FIELDS & set(vals):
                raise UserError(_('Use the Issue, Cancel and Reset to Draft buttons to change the status '
                                  'of a warning letter.'))
            if LOCKED_FIELDS & set(vals) and any(rec.state != 'draft' for rec in self):
                raise UserError(_('An issued or cancelled warning letter cannot be changed. '
                                  'Reset it to draft first.'))
        if 'end_date' in vals and not vals['end_date']:
            raise ValidationError(_('The end date of a warning letter is required.'))
        watchers_before = {}
        if 'watcher_ids' in vals:
            watchers_before = {rec.id: rec._nex_watcher_partners() for rec in self}
        res = super().write(vals)
        if 'attachment_ids' in vals:
            self._nex_link_attachments()
        if 'watcher_ids' in vals:
            for rec in self.filtered(lambda r: r.state == 'issued'):
                removed = watchers_before.get(rec.id, self.env['res.partner']) - rec._nex_follower_partners()
                rec._nex_unsubscribe(removed)
                rec._nex_sync_followers()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_issued(self):
        if any(rec.state == 'issued' for rec in self):
            raise UserError(_('An issued warning letter cannot be deleted. Cancel it first.'))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def _nex_check_flow_rights(self):
        if not self.env.su and not self.env.user.has_group(OFFICER_GROUP):
            raise AccessError(_('Only HR can issue, cancel or reset a warning letter.'))
        self.check_access('write')

    def _nex_lock_rows(self):
        """Lock the rows before a transition, then read the state again."""
        if not self.ids:
            return
        self.flush_recordset()
        self.env.cr.execute('SELECT id FROM nex_warning_letter WHERE id IN %s FOR UPDATE', [tuple(self.ids)])
        self.invalidate_recordset(['state', 'name', 'issued_on'])

    def _nex_flow_write(self, vals):
        return self.with_context(**{FLOW_CONTEXT_KEY: _FLOW_TOKEN}).write(vals)

    def action_issue(self):
        """Issue the warning letter: number, followers, log note and e-mail."""
        self._nex_check_flow_rights()
        self._nex_lock_rows()
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_('Only a draft warning letter can be issued.'))
        for rec in self:
            vals = {'state': 'issued'}
            if not rec.name:
                vals['name'] = rec.company_id._nex_warning_next_number()
            if not rec.issued_on:
                vals['issued_on'] = fields.Datetime.now()
            rec._nex_flow_write(vals)
            rec._nex_sync_followers()
            rec.message_post(
                body=_('Warning letter %(type)s issued to %(employee)s.',
                       type=rec.type_id.name, employee=rec.employee_name),
                subtype_xmlid='mail.mt_note',
            )
            rec._nex_send_issue_email()
        return True

    def action_cancel(self):
        self._nex_check_flow_rights()
        self._nex_lock_rows()
        if any(rec.state not in ('draft', 'issued') for rec in self):
            raise UserError(_('Only a draft or issued warning letter can be cancelled.'))
        self._nex_flow_write({'state': 'cancelled'})
        for rec in self:
            rec._nex_unsubscribe(rec._nex_follower_partners())
        return True

    def action_reset_draft(self):
        """Back to draft. The number is kept: issuing again reuses it."""
        self._nex_check_flow_rights()
        self._nex_lock_rows()
        if any(rec.state != 'cancelled' for rec in self):
            raise UserError(_('Only a cancelled warning letter can be reset to draft.'))
        self._nex_flow_write({'state': 'draft', 'acknowledged_on': False})
        return True

    def action_acknowledge(self):
        """The employee confirms having read his warning letter."""
        for rec in self:
            if not rec.can_acknowledge:
                raise AccessError(_('Only the employee of an issued warning letter can confirm having read it.'))
            rec.sudo()._nex_flow_write({'acknowledged_on': fields.Datetime.now()})
            rec.message_post(body=_('%s confirmed having read the warning letter.', self.env.user.name),
                             subtype_xmlid='mail.mt_note')
        return True

    # ------------------------------------------------------------------
    # Followers, e-mail, attachments
    # ------------------------------------------------------------------

    def _nex_watcher_partners(self):
        self.ensure_one()
        return self.sudo().watcher_ids.user_id.partner_id

    def _nex_follower_partners(self):
        """Partners of the employee and of the watchers (linked users only)."""
        self.ensure_one()
        sudo = self.sudo()
        return (sudo.employee_id.user_id | sudo.watcher_ids.user_id).partner_id

    def _nex_sync_followers(self):
        """Issued letters: the employee and the watchers follow the public
        comments only. Drafts never subscribe them."""
        comment = self.env.ref('mail.mt_comment')
        for rec in self.filtered(lambda r: r.state == 'issued'):
            sudo = rec.sudo()
            partners = rec._nex_follower_partners() - sudo.message_partner_ids
            if partners:
                sudo.message_subscribe(partner_ids=partners.ids, subtype_ids=comment.ids)

    def _nex_unsubscribe(self, partners):
        """Stop the given partners following, except HR users."""
        self.ensure_one()
        partners = partners.filtered(
            lambda p: not any(user.has_group(OFFICER_GROUP) for user in p.sudo().user_ids))
        if partners:
            self.sudo().message_unsubscribe(partner_ids=partners.ids)

    def _nex_email_to(self):
        """Work e-mail of the employee, else the e-mail of his user."""
        self.ensure_one()
        employee = self.sudo().employee_id
        return employee.work_email or employee.user_id.email or ''

    def _nex_email_cc(self):
        self.ensure_one()
        if not self.sudo().company_id.nex_warning_cc_watchers:
            return ''
        emails = []
        for watcher in self.sudo().watcher_ids:
            email = watcher.work_email or watcher.user_id.email
            if email and email not in emails:
                emails.append(email)
        return ','.join(emails)

    def _nex_record_url(self):
        self.ensure_one()
        return '%s/mail/view?model=%s&res_id=%s' % (self.get_base_url(), self._name, self.id)

    def _nex_send_issue_email(self):
        self.ensure_one()
        if not self.sudo().company_id.nex_warning_notify_email:
            return False
        if not self._nex_email_to():
            self.message_post(
                body=_('No e-mail address: the employee was not notified by e-mail.'),
                subtype_xmlid='mail.mt_note',
            )
            return False
        template = self.env.ref('nexa_warning_letter.nexa_mail_template_warning_issued', raise_if_not_found=False)
        if not template:
            return False
        template.sudo().send_mail(self.id, force_send=False)
        return True

    def _nex_link_attachments(self):
        """Link the uploaded files to the letter, so that their access follows
        the access to the letter."""
        Attachment = self.env['ir.attachment']
        for rec in self:
            to_link = Attachment
            for attachment in rec.sudo().attachment_ids:
                if attachment.res_model == self._name and attachment.res_id == rec.id:
                    continue
                if attachment.res_model in (False, self._name) and not attachment.res_id \
                        and attachment.create_uid.id in (self.env.uid, SUPERUSER_ID):
                    to_link |= attachment
                    continue
                raise ValidationError(_('The file %s belongs to another document.', attachment.name))
            if to_link:
                to_link.sudo().write({'res_model': self._name, 'res_id': rec.id})

    # ------------------------------------------------------------------
    # Employee access
    # ------------------------------------------------------------------

    @api.model
    def get_formview_id(self, access_uid=None):
        """Employees without HR rights open the reading view (links of the e-mails)."""
        user = self.env['res.users'].browse(access_uid) if access_uid else self.env.user
        if not user.has_group(OFFICER_GROUP):
            return self.env.ref('nexa_warning_letter.nexa_warning_letter_view_form_my').id
        return super().get_formview_id(access_uid=access_uid)

    def _nex_active_on(self, employee, day=None):
        """Issued warning letters of ``employee`` active on ``day``."""
        day = fields.Date.to_date(day) if day else fields.Date.context_today(self)
        return self.sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'issued'),
            ('effective_date', '<=', day),
            ('end_date', '>=', day),
        ])
