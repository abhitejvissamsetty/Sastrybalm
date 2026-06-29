---
id: TC-0002
priority: High
status: Failed
author: Vinod
module: Geography
---
### Description
A `zone` geography is mapped as a parent for some `region` geographies eg: Step 2 in [TC-0001](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FGeography%2FHierarchical%20Geography%20Validation%20in%20Parent%20Geography). Any `deactivate` action against a geography should check for `dependencies` on it
<u>Pre-conditions</u>
1. After creating a dependent `region` on a `zone` 
2. Navigated back to `geography list view` and 
3. Clicked on a `deactivate action` button against `zone` that was mapped as `parent` in Step 1

| Step | Action                                                                           | Expected Result                                                                                                       | What is happening                                                           | Status   |
| ---- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | -------- |
| 1    | Create a geography that is `zone` eg: South                                      | Create Geography Form should show `parent` field empty.<br>A `zone` named `South` should be created                   |                                                                             | ==PASS== |
| 2    | Create a geography that is `region` eg: TN                                       | Create Geography Form should show `parent` field with Step 1 created zone.<br>A `region` named `TN` should be created |                                                                             | ==PASS== |
| 3    | Navigate to Geography List View and Click on `Deactivate` button against `South` | Should throw a Validation Error that `region` - TN is dependent on the `zone` - South and cannot be `deactivated`     | `zone` - South is getting `in-active` without `dependency validation` check | ==FAIL== |
