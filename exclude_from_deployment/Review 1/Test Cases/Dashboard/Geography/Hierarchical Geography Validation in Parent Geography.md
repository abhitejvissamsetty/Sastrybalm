---
id: TC-D-0001
priority: Medium
status: Failed
author: Vinod
module: Geography
---
### Description
A `zone` geography should see `empty parent` field. A `region` geography should see only `zone` parents. A `territory` geography should see only `region` parents
<u>Pre-conditions</u>
- None

| Step | Action                                                | Expected Result                                                                                                       | Status   |
| ---- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | -------- |
| 1    | Create a geography that is `zone` eg: South           | Create Geography Form should show `parent` field empty.<br>A `zone` named `South` should be created                   | ==PASS== |
| 2    | Create a geography that is `region` eg: TN            | Create Geography Form should show `parent` field with Step 1 created zone.<br>A `region` named `TN` should be created | ==PASS== |
| 3    | Create a geography that is `territory` eg: Coimbatore | Create Geography Form should show `parent` field with newly created`region` only and not the `zone` from Step 1       | ==FAIL== |
