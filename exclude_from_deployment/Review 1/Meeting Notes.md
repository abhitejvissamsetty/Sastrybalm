- `Geography, Positions, Beats, Outlets` are maintained in mariadb
- `users` are maintained in mariadb but `fetch` from `ZAP` for `employee-id` and `validation of email` against all `ZAP, CONNECT, CMMS` backends
- `company profile` is also maintained in mariadb but `validation` of `integration settings` against all `ZAP, CONNECT, CMMS` backends
- `products` are also maintained in mariadb but `fetched` from `ZAP & CMMS`
### Procurement related
- Some Items from `CMMS` System can be done without `Procurement`/`Material Requests` flow.
- These items can be `Asset Capitalized` by the `Rep` himself
### Data involved between different systems
### 1
```
ZAP
----
1) Invoices
	1.1) Outlet Details - Address, Contact
	1.2) Order Item Details with Quantity
2) Payments
3) Journal Entries - Payment Denomination Submission
4) Expenses
5) Timesheets
```
### 2
```
CONNECT
-------
1) Orders
   1.1) Outlet Details - Address, Contact
   1.2) Order Item Details with Quantity
```
### 3
```
CMMS
-----
1) Material Requests
2) Asset Capitalizations
```

### Transactional Data
#### Payments
- The New `Payment` record need to have `Order` of type `ZAP Invoice` and `unpaid` status as reference. 
#### Order
- GST Calculation not working properly. PFB Screenshot
- ![[Pasted image 20260516125843.png]]
#### Missing Transactional Data
- Payment Submission Records
	- `Payments` are group of records that signifies payment collection by`Rep` from `Outlet` for an `Order`
	- While `Payment Submissions`are records that are a group of `Payments` for which `Rep` accumulates and submit them back to `Company` which will be posted as a `Journal Entry` in `ZAP` System
- Asset Capitalizations
	- `Material Requests` are group of records that signifies the `proposal by outlet to host a marketing material that needs to be procured from a vendor`
	- `Asset Capitalizations` are group of records that signifies the `Material being hosted at Outlet by Rep or Vendor Technician`. Vendor Technician or Rep picks the item from `CMMS` system assigned `Warehouse` and `hoist` near the `Outlet` 
### Logic for Attendance and Timesheets related Approvals
- For an Attendance record to valid, respective Timesheet must be created (1 attendance can be mapped to multiple Timesheet Records but within same date)
- Attendance Dashboard or List View should filter based on "Approval Status"
- Detail action Button
	- Detail Page that shows clear view of `Activities Carried` in that particular day- [Outlets Visited, Orders Taken, Invoices Generated, Payments Collected, Material Requests raised, Asset Capitalisations] (Arrange them in left pane). Beside that, Show timesheets and its activities in a list view (may be in right pane). Each Timesheet entry have 2 action buttons - Approve Timesheet and Reject Timesheet. (Reapprove on Rejected Timesheets)
	- Calculate `Total Hours based on Timesheets` vs `Activity based Hours` vs `Checkout Time - Checkin Time`. Based on this, Auto calculate and Suggest Attendance - Full Day / Half Day
### Sales Performance
<u>Order Performance</u>
- MTD, LMTD, Custom Date Range
- Invoice Performance, Connect Order Performance
<u>Payment Performance</u>
- MTD, LMTD, Custom Date Range
- Credit Invoices, Cash Invoices
<u>Payment Submission Performace</u>
- Ledger based
- Pending Approval Amount 
- Total Invoice Amount - Total Cleared Amount = `Suspense Amount`
### Rep Performance
<u>Hours Spent Performance</u>
- MTD, LMTD, Custom Date Range
- Original Field based Hours vs Timesheet Hours
<u>Compliance Performance</u>
- MTD, LMTD, Custom Date Range
- Visit Compliance
	- Telephonic vs Out of Range Orders vs In-Location Order
- Some more
<u>Marketing Performance</u>
- MTD, LMTD, Custom Date Range
- Asset Capitalizations Performance
- Marketing Requests Performance

## Features missing in Current Dashboard
### 1. Asset Capitalizations feature for `Rep`
### 2. `Vendor` roles who work on `Material Requests` in a procurement workflow
### 3. Auto flagging