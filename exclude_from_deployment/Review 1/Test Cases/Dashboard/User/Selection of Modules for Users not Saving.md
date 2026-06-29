---
id: TC-D-0007
priority: Medium
status: Failed
author: Vinod
module: Users
---
### Description
A user created with a role and certain "modules" are enabled. An edit on same user is done. The modules that are selected are showing 'null'
<u>Pre-conditions</u>
1. Edit a Newly created user

| Step | Action                                                              | Expected Result                                             | What is happening                           | Status   |     |
| ---- | ------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------- | -------- | --- |
| 1    | Click on Add User from Users List View                              | Should open "Add User" Form                                 |                                             | ==PASS== |     |
| 2    | Select some role like `Field Rep`                                   | NA                                                          |                                             | ==PASS== |     |
| 3    | Select some modules like [Invoicing, Payments, Connect, Timesheets] | Check boxes against the module should be 'ticked'           |                                             | ==PASS== |     |
| 4    | Save the `User`                                                     | Navigate back to 'User' list view                           |                                             | ==PASS== |     |
| 5    | Click on `Edit` action                                              | Should Open the Saved User form with Step 1,2,3 filled data | Step 3 : `modules` selected are not showing | ==FAIL== |     |
