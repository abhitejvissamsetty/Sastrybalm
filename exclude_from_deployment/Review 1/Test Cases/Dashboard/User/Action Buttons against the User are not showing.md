---
id: TC-D-0006
priority: Medium
status: Failed
author: Vinod
module: Users
---
### Description
A user created with a role and certain "modules" are selected against. 
<u>Pre-conditions</u>
1. Edit a Newly created user

| Step | Action                                                              | Expected Result                                                                  | What is happening                               | Status   |
| ---- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------- | -------- |
| 1    | Click on Add User from Users List View                              | Should open "Add User" Fo                                                        |                                                 | ==PASS== |
| 2    | Select some role like `Field Rep`                                   |                                                                                  |                                                 | ==PASS== |
| 3    | Select some modules like [Invoicing, Payments, Connect, Timesheets] | Check boxes against the module should be 'ticked'                                |                                                 | ==PASS== |
| 4    | Save the User                                                       | Navigated back to Users list view                                                |                                                 | ==PASS== |
| 5    | Check the `action` buttons available                                | [Edit, Deactivate, Activation Code, Register] action buttons should be available | Only [Edit, Deactivate] action buttons availble | ==FAIL== |

