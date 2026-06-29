---
id: TC-D-0008
priority: Medium
status: Failed
author: Vinod
module: Positions
---
### Description
An `L3 Position` should see only `L4 Position` in `reports_to` field. While `L2 Postion` should see only `L3 positions` in `reports_to` field and hence `L1 Position` should see `L2 Position`
<u>Pre-conditions</u>
1. Create any Position (L4/L3/L2)

| Step | Action                                                    | Expected Result                          | What is happening                 | Status   |
| ---- | --------------------------------------------------------- | ---------------------------------------- | --------------------------------- | -------- |
| 1    | Click on Add Postion from Positions List View             | Should open "Add Position" Form          |                                   | ==PASS== |
| 2    | Select Level = `L3`. Now, click on `reports_to` drop-down | Should show filtered `L4` positions only | All L4/L3/L2/L1 positions showing | ==FAIL== |
| 3    | Select Level = `L2`. Now, click on `reports_to` drop-down | Should show filtered `L3` positions only | All L4/L3/L2/L1 positions showing | ==FAIL== |
