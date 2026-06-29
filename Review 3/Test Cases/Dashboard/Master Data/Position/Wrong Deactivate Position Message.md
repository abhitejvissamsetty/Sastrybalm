---
id: TC-D-0041
status: Failed
module: Positions
author: Vinod
priority: Medium
---
### Description
Create a hierarchy of `Positions` [L4,L3,L2,L1]. Establish dependency (reports_to) on all these `Positions`. Now, try to deactivate the `L4 Position` (where the dependent L3, L2, L1 exists). Error message showing is `wrong` 
```
Cannot deactivate 'TN ZSM' because it has active direct reports
```

![[Pasted image 20260618170054.png]]
