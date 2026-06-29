---
id: TC-D-0042
author: Vinod
module: Positions
status: Failed
priority: Medium
---
### Description
Ensure some Beats are added in the `backend`. Add these Beats to any `L1 Position` using `Attach Beats` action button. Now, click on `Deactivate` on the `L1 Position`. 

> [!EXPECTED]
> Error should be thrown that Dependent Beats exist

> [!PRESENT]
> It is simply deactivating without checking for the dependencies

