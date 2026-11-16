from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestNexaWarningLetter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # English texts are checked, whatever the main language of the database
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, lang='en_US'))
        cls.company = cls.env.company
        cls.company.write({'nex_warning_notify_email': True, 'nex_warning_cc_watchers': True,
                           'email': 'hr@example.com'})
        cls.company._nex_warning_init()
        cls.officer = new_test_user(cls.env, lang='en_US', login='nex_wl_officer', groups='hr.group_hr_user',
                                    company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.manager = new_test_user(cls.env, lang='en_US', login='nex_wl_manager', groups='hr.group_hr_manager',
                                    company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.emp_user = new_test_user(cls.env, lang='en_US', login='nex_wl_employee', groups='base.group_user',
                                     email='employee@example.com',
                                     company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.watcher_user = new_test_user(cls.env, lang='en_US', login='nex_wl_watcher', groups='base.group_user',
                                         company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.other_user = new_test_user(cls.env, lang='en_US', login='nex_wl_other', groups='base.group_user',
                                       company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        Employee = cls.env['hr.employee']
        cls.employee = Employee.create({'name': 'NEX WL Employee', 'user_id': cls.emp_user.id,
                                        'work_email': 'employee@example.com'})
        cls.watcher = Employee.create({'name': 'NEX WL Manager', 'user_id': cls.watcher_user.id,
                                       'work_email': 'manager@example.com'})
        cls.other = Employee.create({'name': 'NEX WL Other', 'user_id': cls.other_user.id})
        Type = cls.env['nex.warning.letter.type']
        cls.type_wl1 = Type.search([('company_id', '=', cls.company.id), ('sequence', '=', 2)], limit=1)
        cls.Letter = cls.env['nex.warning.letter'].with_user(cls.officer)
        cls.today = fields.Date.context_today(cls.env['nex.warning.letter'])

    def _letter(self, employee=None, **vals):
        return self.Letter.create(dict({
            'employee_id': (employee or self.employee).id,
            'type_id': self.type_wl1.id,
            'notes': 'Late three times this month.',
            'internal_note': 'Discussed with the manager.',
            'watcher_ids': [(6, 0, self.watcher.ids)],
        }, **vals))

    def _mails(self, letter):
        return self.env['mail.mail'].search([('model', '=', 'nex.warning.letter'), ('res_id', '=', letter.id)])

    def test_default_types_and_numbering(self):
        types = self.env['nex.warning.letter.type'].search([('company_id', '=', self.company.id)])
        self.assertEqual(len(types), 4)
        self.assertEqual(self.type_wl1.validity_months, 6)
        letter = self._letter()
        self.assertEqual(letter.state, 'draft')
        self.assertFalse(letter.name)
        self.assertEqual(letter.end_date, self.today + relativedelta(months=6) - timedelta(days=1))
        letter.action_issue()
        self.assertEqual(letter.state, 'issued')
        self.assertTrue(letter.name.startswith('WL/%s/' % self.today.year))
        self.assertTrue(letter.issued_on)
        second = self._letter(employee=self.other)
        second.action_issue()
        self.assertNotEqual(second.name, letter.name)

        other_company = self.env['res.company'].create({'name': 'NEX WL Company B'})
        self.assertEqual(self.env['nex.warning.letter.type'].search_count(
            [('company_id', '=', other_company.id)]), 4, 'a new company gets the default types')

    def test_issue_sends_the_email(self):
        letter = self._letter()
        letter.action_issue()
        mails = self._mails(letter)
        self.assertEqual(len(mails), 1)
        addresses = set(mails.recipient_ids.mapped('email')) | {
            e.strip() for e in ((mails.email_to or '') + ',' + (mails.email_cc or '')).split(',') if e.strip()}
        self.assertIn('employee@example.com', addresses)
        self.assertIn('manager@example.com', addresses, 'copy to the watcher')
        self.assertIn('NEX WL Employee', mails.subject)
        self.assertIn(self.emp_user.partner_id, letter.message_partner_ids)
        self.assertIn(self.watcher_user.partner_id, letter.message_partner_ids)

        self.company.nex_warning_notify_email = False
        second = self._letter(employee=self.other)
        second.action_issue()
        self.assertFalse(self._mails(second))

    def test_issued_letter_is_locked(self):
        letter = self._letter()
        letter.action_issue()
        with self.assertRaises(UserError):
            letter.notes = 'Changed'
        with self.assertRaises(UserError):
            letter.write({'state': 'draft'})
        with self.assertRaises(UserError):
            letter.unlink()
        letter.action_cancel()
        self.assertEqual(letter.state, 'cancelled')
        letter.action_reset_draft()
        self.assertEqual(letter.state, 'draft')
        number = letter.name
        letter.notes = 'Corrected'
        letter.action_issue()
        self.assertEqual(letter.name, number, 'the number is kept')
        with self.assertRaises(UserError):
            self.Letter.create({'employee_id': self.employee.id, 'type_id': self.type_wl1.id,
                                'state': 'issued'})

    def test_checks(self):
        with self.assertRaises(ValidationError):
            self._letter(watcher_ids=[(6, 0, self.employee.ids)])
        with self.assertRaises(ValidationError):
            self._letter(effective_date=self.today, end_date=self.today - timedelta(days=1))
        with self.assertRaises(ValidationError):
            self.env['nex.warning.letter.type'].create({'name': self.type_wl1.name})

    def test_validity(self):
        active = self._letter()
        expired = self._letter(effective_date=self.today - relativedelta(years=1),
                               end_date=self.today - timedelta(days=1))
        upcoming = self._letter(effective_date=self.today + timedelta(days=5))
        self.assertEqual(active.validity_status, 'active')
        self.assertEqual(expired.validity_status, 'expired')
        self.assertEqual(upcoming.validity_status, 'upcoming')
        letters = active | expired | upcoming
        Letter = self.Letter.with_context(active_test=False)
        self.assertEqual(Letter.search([('id', 'in', letters.ids), ('validity_status', '=', 'active')]), active)
        self.assertEqual(Letter.search([('id', 'in', letters.ids), ('validity_status', '!=', 'active')]),
                         expired | upcoming)
        self.assertEqual(Letter.search([('id', 'in', letters.ids),
                                        ('validity_status', 'in', ['expired', 'upcoming'])]), expired | upcoming)
        active.action_issue()
        self.assertEqual(self.employee.with_user(self.officer).nex_active_warning_count, 1)
        self.assertEqual(self.employee.with_user(self.officer).nex_warning_letter_count, 3)

    def test_employee_reads_own_issued_letters(self):
        own = self._letter()
        draft = self._letter()
        other = self._letter(employee=self.other, watcher_ids=[(5, 0, 0)])
        (own | other).action_issue()
        Letter = self.env['nex.warning.letter'].with_user(self.emp_user)
        self.assertEqual(Letter.search([]), own, 'own issued letters only, not drafts or others')
        self.assertTrue(draft)
        read = Letter.browse(own.id).read(['name', 'notes', 'employee_name', 'type_id'])
        self.assertEqual(read[0]['notes'], 'Late three times this month.')
        with self.assertRaises(AccessError):
            Letter.browse(own.id).read(['internal_note'])
        with self.assertRaises(UserError):
            Letter.browse(own.id).write({'notes': 'No'})
        with self.assertRaises(AccessError):
            Letter.browse(own.id).write({'watcher_ids': [(5, 0, 0)]})
        with self.assertRaises(AccessError):
            Letter.create({'employee_id': self.employee.id, 'type_id': self.type_wl1.id})
        # the watcher reads it too, another employee does not
        self.assertEqual(self.env['nex.warning.letter'].with_user(self.watcher_user).search([]), own)
        self.assertFalse(self.env['nex.warning.letter'].with_user(self.other_user).search(
            [('id', '=', own.id)]))
        # the employee replies in the chatter
        Letter.browse(own.id).message_post(body='I understand.', message_type='comment',
                                           subtype_xmlid='mail.mt_comment')

    def test_acknowledge(self):
        letter = self._letter()
        letter.action_issue()
        as_watcher = letter.with_user(self.watcher_user)
        self.assertFalse(as_watcher.can_acknowledge)
        with self.assertRaises(AccessError):
            as_watcher.action_acknowledge()
        as_employee = letter.with_user(self.emp_user)
        self.assertTrue(as_employee.can_acknowledge)
        as_employee.action_acknowledge()
        self.assertTrue(letter.acknowledged_on)
        self.assertFalse(as_employee.can_acknowledge)
        with self.assertRaises(UserError):
            letter.write({'acknowledged_on': False})

    def test_views_for_each_role(self):
        Letter = self.env['nex.warning.letter']
        self.assertEqual(Letter.with_user(self.emp_user).get_formview_id(),
                         self.env.ref('nexa_warning_letter.nexa_warning_letter_view_form_my').id)
        self.assertNotEqual(Letter.with_user(self.officer).get_formview_id(),
                            self.env.ref('nexa_warning_letter.nexa_warning_letter_view_form_my').id)
        for user, model, view_type, view in (
            (self.officer, 'nex.warning.letter', 'form', False),
            (self.officer, 'nex.warning.letter', 'list', False),
            (self.officer, 'nex.warning.letter', 'search', False),
            (self.officer, 'nex.warning.letter', 'pivot', False),
            (self.manager, 'nex.warning.letter.type', 'list', False),
            (self.officer, 'hr.employee', 'form', False),
            (self.emp_user, 'nex.warning.letter', 'form', 'nexa_warning_letter.nexa_warning_letter_view_form_my'),
            (self.emp_user, 'nex.warning.letter', 'list', 'nexa_warning_letter.nexa_warning_letter_view_list_my'),
        ):
            view_id = self.env.ref(view).id if view else False
            arch = self.env[model].with_user(user).get_views([(view_id, view_type)])
            self.assertTrue(arch['views'][view_type]['arch'])
        arch = self.env['res.config.settings'].get_views([(False, 'form')])
        self.assertIn('nex_warning_notify_email', arch['views']['form']['arch'])

    def test_printable_letter(self):
        letter = self._letter()
        letter.action_issue()
        html, _type = self.env['ir.actions.report']._render_qweb_html(
            'nexa_warning_letter.nexa_report_warning_letter', letter.ids)
        html = html.decode()
        self.assertIn(letter.name, html)
        self.assertIn('NEX WL Employee', html)
        self.assertIn('Late three times this month.', html)
        self.assertNotIn('Discussed with the manager.', html, 'never the internal note')

    def test_standard_employee_flows_untouched(self):
        letter = self._letter()
        letter.action_issue()
        self.employee.with_context(no_wizard=True).action_archive()
        self.assertFalse(self.employee.active)
        self.assertEqual(letter.with_user(self.officer).employee_id, self.employee,
                         'the letter keeps its archived employee')
        self.other.with_context(no_wizard=True).action_archive()
        self.assertFalse(self.other.active)
        self.other.action_unarchive()
        self.assertTrue(self.other.active)
        employee = self.env['hr.employee'].create({'name': 'NEX WL Plain'})
        employee.unlink()
