---
id: TC-D-0005
priority: Medium
status: Failed
author: Vinod
module: Users
---
### Description
An admin should see following roles to be mapped for a user [Field Rep, Territory Manager, Admin, Vendor Technician, Vendor Admin, QC Manager]
<u>Pre-conditions</u>
1. Edit or New User Form to be Opened

| Step | Action                                                              | Expected Result                                                                                                 | What is happening                        | Status   |
| ---- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | -------- |
| 1    | Click on Add User from Users List View                              | Should open "Add User" Form                                                                                     |                                          | ==PASS== |
| 2    | Check if the Basic Details like Email, Name, other fields available | Should show all the fields                                                                                      |                                          | ==PASS== |
| 3    | Check if `Phone` is mandatory                                       | `Phone Number` should be mandatory                                                                              | `Phone Number` is not mandatory          | ==FAIL== |
| 4    | Check the `Roles` that can be mapped to `user`                      | [Field Rep, Territory Manager, Admin, Vendor Technician, Vendor Admin, QC Manager] should be shown in drop-down | [Field Rep, Manager, Admin] only visible | ==FAIL== |
