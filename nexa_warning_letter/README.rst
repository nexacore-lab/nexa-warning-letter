===================
Nexa Warning Letter
===================

Warning letters for employees, for Odoo 19.0 (Community or Enterprise). Free
and open source (LGPL-3).

* **Types**: documented verbal warning, warning letter 1, 2 and 3 are created
  for each company, each with a default validity that fills the end date.
* **Issue**: a draft letter is issued with its number (one numbering per
  company) and locked. The employee receives it by e-mail, the watchers (for
  example the manager) receive a copy and follow the comments.
* **Employees**: they read their own warning letters, and the ones they watch,
  in *My Warning Letters*, confirm that they have read them and reply in the
  chatter. Drafts and the internal note of HR are never shown to them.
* **PDF**: a printable warning letter with signature boxes.
* **Follow-up**: validity (active, upcoming, expired), "not read yet" filter,
  pivot view and a counter on the employee form.

Requirements
============

* Odoo 19.0 with the Employees application (``hr``).
* No Python package to install, no external service.

Installation
============

1. Copy the ``nexa_warning_letter`` folder into your addons path.
2. Restart Odoo and update the apps list.
3. Install **Nexa Warning Letter**.

Configuration
=============

**Settings > Employees > Warning Letters**: e-mail to the employee, copy to the
watchers, numbering and the warning letter types.

Roles: **Employees: Officer** creates, issues and cancels the letters;
**Employees: Administrator** also deletes them and manages the types; every
employee with a user reads his own letters.

Usage
=====

1. **Employees > Warning Letters > Warning Letters**: create a letter, choose
   the employee, the type and the watchers, write the details, then **Issue**.
2. The employee opens **Employees > Warning Letters > My Warning Letters** (or
   the link of the e-mail) and clicks **I Have Read It**.
3. **Print** gives the PDF letter to sign.

Good to know
============

* The module only adds menus, a button on the employee form and a settings
  block; the standard Employees application keeps working as before.
* An issued letter cannot be changed or deleted: cancel it, reset it to draft
  and issue it again (the number is kept).

Support
=======

halo@nexacoresolution.id

License
=======

GNU Lesser General Public License v3 (LGPL-3). See the ``LICENSE`` file.

Copyright (c) 2026 NexaCore Solution.
