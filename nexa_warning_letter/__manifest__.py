{
    'name': 'Nexa Warning Letter',
    'version': '19.0.1.0.0',
    'summary': 'Warning letter, employee warning letter, disciplinary action, employee discipline, '
               'disciplinary letter, written warning, verbal warning, final warning, reprimand, '
               'employee reprimand, HR warning, warning letter template, warning letter PDF, '
               'disciplinary record, employee misconduct, surat peringatan, SP1, SP2, SP3, '
               'teguran karyawan, HRIS, free',
    'description': """
Nexa Warning Letter
===================
HR issues warning letters (documented verbal warning, warning letter 1 to 3)
to employees:

* warning letter types per company, each with a default validity that fills
  the end date;
* draft, issued and cancelled letters; an issued letter is locked and gets its
  number, one numbering per company;
* the employee receives the letter by e-mail, the appointed watchers (for
  example the manager) receive a copy and follow the comments;
* employees read their own warning letters, and the ones they watch, in
  Employees > Warning Letters > My Warning Letters, confirm that they have read
  them and reply in the chatter;
* printable warning letter (PDF) with signature boxes;
* an internal note that only HR can read.

The module adds menus, a button on the employee form and a settings block; the
standard Employees application keeps working as before. It uses no external
service.
""",
    'category': 'Human Resources',
    'author': 'NexaCore Solution',
    'maintainer': 'NexaCore Solution',
    'website': 'https://nexacoresolution.id',
    'support': 'halo@nexacoresolution.id',
    'license': 'LGPL-3',
    'images': ['images/main_screenshot.png'],
    'depends': [
        'mail',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/nexa_warning_letter_security.xml',
        'data/nexa_mail_template_data.xml',
        'report/nexa_warning_letter_report.xml',
        'views/nexa_warning_letter_type_views.xml',
        'views/nexa_warning_letter_views.xml',
        'views/nexa_hr_employee_views.xml',
        'views/nexa_res_config_settings_views.xml',
        'views/nexa_warning_letter_menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': True,
}
