---
tags:
status: In-Progress
language: Python
date: 14 May 2026
---
## Case 1: Company Profile
### Objective:
UI should have proper data fields to let admin input details for api backends (ZAP, CMMS, CONNECT)

<u>Good</u>
- Profile Name and Profile Code
- API Endpoint
- API Key
	- <u>Clarification</u>: API Key here follows the pattern `api_key`:`api_secret`

<u>Bad</u> (Expected but not there)
- Each "Integration Setting" should accept input for "Backend Company" name
- A "Test Connection" button that tests the "Integration Settings"
- `Product Mapping` and `Account Mapping` that acts as a base for proper api calls to backend is missing [ER Diagram](https://mermaid.ai/live/edit#pako:eNqFk11vgjAUhv8KOddoyPio487gTBankmVebCEhDVQkSktKSabIf19LZBEFveCifc57Pt4eKohYTMAFwmcpTjjOAhoIb730p6vv0P9cz98_3rRKXQaiEDyliZZztk0PJKQ4I71ApdT8RYedcB7iPA0JjXOWUnEHI5blmB6brCE-pLjohESMDusVfKbPsuJBAkWfZGgn2JNjWJCIE9Hb4BBu63d53QTJT1o923hf4XLqD9jduDpf3LK4jMT9U6hmW9hv5gOqWr3DTadTz1tvVn1d4ihiJRVPlmLesxQX4cCTD9PG0Ftc963v-TwasUq7ttjVArn5VOCUFgE8EF1P3BWBDglPY3AFL4kOGeEZVkeQxmgyUuyItAKUKMZ8r6rUUiNX7IexrJVxViY7cLf4UMhTmcdYkMuf-H_L5c4S7qlJwbWbFOBW8Auu6Vhj00HIQOjFcWzbtHQ4gmtNxpaJLGQbFnox0KtZ63BqihrjCbLrP6wsdrY)

<u>Suggestions</u>
- Lets include `Tags` field in Company Profile
	- When a Company Profile is tested with `Integration Settings` but the Integration details are wrong. Mark `Error`
	- When Company Profile `ZAP Integration` is tested and working, add tag `ZAP-READY` to Company Profile, similarly `CMMS-READY`, `CONNECT-READY`
- This `Tags` field will be used when allocating Modules - `Invoice, Connect, Payments, CMMS Retail, CMMS Vendor` for `User` in `Master Management`
- Lets add `deactivate` and `activate` toggle to `Company Profile` similar to `Geography`
## Case 2: System Configuration

### Objective:
Define System Wide defaults that determine the behaviour of `MOBILE BACKEND` with `MOBILE CLIENTS/FRONTEND` and `API BACKENDS`

<u>Good</u>
- Mobile Frontend Behaviour like `Sync Interval` & `GPS Threshold`

<u>Bad</u>
- `Payment Settings` are defined in `user masters` when `invoicing` module is enabled and not in `system configuration`
- `API Sync Settings` like intervals to `fetch` the data or intervals/schedules to `post` the data missing. Maybe we can define these `api sync settings` under the `integration settings` of `Company Profile masters`
## Case 3: Products Catalogue
### Objective:
Requires an UI to manage "Products" to be displayed to "Mobile Users"
<u>Bad</u>
- This UI should be defined in `Company Profile masters`. As different `Company Profiles` will have different `Products`
<u>Good</u>
- Having a `menu shortcut` in `hamburger menu`. Lets have a shortcut but when clicked we shall show a message that `Products` catalogue to be configured in `Company Profile`
<u>Suggestions</u>:
- We shall have a `Filter` for `Company Profile`. When selected, will load the `Product Catalog`
## Case 4: Outlets Catalogue
### Objective
Requires an UI to manage `Outlets` that the `user` should be able to visit
<u>Good</u>
- [List View, Import, Export] options
- [Beat] Filter
<u>Bad</u>
- Statuses for Outlet will be [Active, In-active] only it should not have multiple statuses like [here](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FScreenshots%2FScreenshot%20From%202026-05-14%2021-13-47.png) . Need an "Action" button to "Disable". `In-active` Outlets can have a "null" beat. `Active` Outlets should be validated for a mandatory `Beat`
- Need `GSTIN` field to store `GST` of the outlet
- `mobile_no` should be validated for `unique phone number`
- Missing `channel` drop-down
- Missing `shop-type` drop-down
- Mandatory `beat` and `territory`. If `territory` is selected first, filter beats that are linked to that `territory` and if `beat` is selected first, auto-populate `territory` field. `beat` and `territory` fields must be `Autocomplete` and not `drop-down`
- `GPS coordinates` should be non-editable and usually `read-only`. Edit to the coordinates can be done by `field users` only through `approval` mechanism
- Missing `external_id` that maps `outlet` to `Fieldassist IDs` [ER Diagram]([https://mermaid.live/edit#pako:eNp1U9tu4jAQ_RXLzxQRQknIWy-0XbUSqEsfdoUUGTyEURM7HTsVlPLvtVkoUuP1U-ZyzlzOZMeXWgLPONAtioJENVfMvcnL7Gk8Y7t_ln_GEqqC6caWYHOPYtNHNucvCt8aYL8kKIsrBJrz_4GUqMAhnuGtQQIZSASqc5QuZ1Jb1EqUDDYWyH8QrIBALSEAI7ACS6Dcbmtf4UZYKDThh_AsAcByLZSC0qXeonctGp94cocAWlmxtHkNZBzjz3ClF65-rppqAfS9lACPkJLAmDY_2m3Laaybo-WtUfntt_yFsecGZmLDMCjJQusShGJocjcQvvt9_XaFGsNWpSgCPS9AHAW_84I_oXplVjNhDBYKJLt28RNsPz8u53p8FTqfM9f0MRz0R_KD6348uX--mj78CRAebirAVcK7EzLQ0-fnxYXenQ48cwMdtEVlTjOcy7VzS710msgc3VXxDi8IJc8sNdDhFVAlvMkPXc65XYMbhXuYFPTq6fcOUwv1V-vqBCPdFGuerURpnNXU0vEff8XvFFAS6EY3yvJsdGDg2Y5veBalSTcZpqPLNI17w2gYpx2-5VkcRd1-nPTjy0EcpXGS7Dv841Cz102iKI0Gab-XDIeDwWj_Ba-mQLE](https://mermaid.live/edit#pako:eNqFU9tu4jAQ_RXLz4CScE3eaEu7q1YCdenDVkiRwUMYNbHTsVPRUv59bRaKVLxaP9kzc85cznjHV1oCzzjQDYqCRLVQzJ3p0_xhMme7vy9_jCVUBdONLcHmHsVm92zBnxS-NsB-SlAW1wi04P8CKVGBQzzCa4MEMhAIVOcoXcy0tqiVKBlsLZC_EKyBQK2AWc2ex7MQ-hj7f4o16YrdIpRybAwaGyAjsAJLoNy-177qa2Gh0IQfwtMGAKuNUApKF3qD3rRsfODJHAJoZcXK5jWQcYzf3ZVeuvy5aqol0NegAzxCSgJjLvnRvl8YjXV9XFhrVF7RC3th7LmAudgyDMq81LoEoRia3DWEb35ev1yixrB1KYpAzUsQxyW69Uv0gOrF6yqcGoUCya6c_wTbL47DuZqMQyt55prdh51-8b5x3U2md4_j2Y_fAcLDnga4SnhzQgZq-vxst_Xu9Gky19BBW1Tm1MM53WVsqVdOE5mj2yre4gWh5JmlBlq8AqqEf_JDlQtuN-Ba4R4mBb14-r3D1EI9a12dYKSbYsOztSiNezW1dPzH7_1ldR9BAl3rRlmeJUl8IOHZjm95Nhx2om40GET9_mCUxHG_xd951o77aScZplHa7abDNB1F_X2Lfxzyxp0oGfV6STLoDqJuEke9_R_Tb17F)
- `Address`. Add another field `pincode` [ER Diagram]([https://mermaid.live/edit#pako:eNp1U9tu4jAQ_RXLzxQRQknIWy-0XbUSqEsfdoUUGTyEURM7HTsVlPLvtVkoUuP1U-ZyzlzOZMeXWgLPONAtioJENVfMvcnL7Gk8Y7t_ln_GEqqC6caWYHOPYtNHNucvCt8aYL8kKIsrBJrz_4GUqMAhnuGtQQIZSASqc5QuZ1Jb1EqUDDYWyH8QrIBALSEAI7ACS6Dcbmtf4UZYKDThh_AsAcByLZSC0qXeonctGp94cocAWlmxtHkNZBzjz3ClF65-rppqAfS9lACPkJLAmDY_2m3Laaybo-WtUfntt_yFsecGZmLDMCjJQusShGJocjcQvvt9_XaFGsNWpSgCPS9AHAW_84I_oXplVjNhDBYKJLt28RNsPz8u53p8FTqfM9f0MRz0R_KD6348uX--mj78CRAebirAVcK7EzLQ0-fnxYXenQ48cwMdtEVlTjOcy7VzS710msgc3VXxDi8IJc8sNdDhFVAlvMkPXc65XYMbhXuYFPTq6fcOUwv1V-vqBCPdFGuerURpnNXU0vEff8XvFFAS6EY3yvJsdGDg2Y5veBalSTcZpqPLNI17w2gYpx2-5VkcRd1-nPTjy0EcpXGS7Dv841Cz102iKI0Gab-XDIeDwWj_Ba-mQLE](https://mermaid.live/edit#pako:eNqFU9tu4jAQ_RXLz4CScE3eaEu7q1YCdenDVkiRwUMYNbHTsVPRUv59bRaKVLxaP9kzc85cznjHV1oCzzjQDYqCRLVQzJ3p0_xhMme7vy9_jCVUBdONLcHmHsVm92zBnxS-NsB-SlAW1wi04P8CKVGBQzzCa4MEMhAIVOcoXcy0tqiVKBlsLZC_EKyBQK2AWc2ex7MQ-hj7f4o16YrdIpRybAwaGyAjsAJLoNy-177qa2Gh0IQfwtMGAKuNUApKF3qD3rRsfODJHAJoZcXK5jWQcYzf3ZVeuvy5aqol0NegAzxCSgJjLvnRvl8YjXV9XFhrVF7RC3th7LmAudgyDMq81LoEoRia3DWEb35ev1yixrB1KYpAzUsQxyW69Uv0gOrF6yqcGoUCya6c_wTbL47DuZqMQyt55prdh51-8b5x3U2md4_j2Y_fAcLDnga4SnhzQgZq-vxst_Xu9Gky19BBW1Tm1MM53WVsqVdOE5mj2yre4gWh5JmlBlq8AqqEf_JDlQtuN-Ba4R4mBb14-r3D1EI9a12dYKSbYsOztSiNezW1dPzH7_1ldR9BAl3rRlmeJUl8IOHZjm95Nhx2om40GET9_mCUxHG_xd951o77aScZplHa7abDNB1F_X2Lfxzyxp0oGfV6STLoDqJuEke9_R_Tb17F). For `connect` system `order` module to work, `pincode` is mandatory . We can use openstreetmap's nominatim - reverse geo-coding to fetch the address
## Case 5: Approvals Menu
### Objective:
Requires an UI to `Approve` or `Reject` - [Outlet Edit, Time-sheet Approval, Payment Denomination Approval, CMMS Material Requests]
<u>Good</u>
- We have `Alerts` menu item in `Hamburger Menu` which we can use to show these `Approval Notifcations`
<u>Bad</u>
- Could not figure proper UI for seeing `Approval Requests`
## Case 6: Back-end Alerts
### Objective:
Requires an UI to see updates on `API based backend sync` docs
<u>Good</u>
- We have `Alerts` menu item in `Hamburger Menu` which we can use to show these `Backend Alerts`
<u>Bad</u>
- Could not figure proper UI for seeing `Backend Alerts`
## Case 6: Geography Masters
### Objective:
Requires an UI to list, add, edit, deactivate Geographies
<u>Good</u>
- `Action` buttons available. 
	- `Deactivate` working
	- `Edit` working
- `Filters`
<u>Bad</u>
- Failed Test Cases
	- [TC-D-0001](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FGeography%2FHierarchical%20Geography%20Validation%20in%20Parent%20Geography)
	- [TC-D-0002](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FGeography%2FDeactivating%20a%20Higher%20Level%20Geography)
	- [TC-D-0003](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FGeography%2FActivating%20a%20Deactivated%20Geography)
	- [TC-D-0004](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FGeography%2FEditing%20a%20Deactivated%20Geography)
## Case 7: Users Masters
### Objective:
Requires an UI to list, add, edit, deactivate Users
<u>Good</u>
- Basic Details like [Name, Email, Phone, Password]
- Module Selection using a dedicated section in User Form
- Master `admin` is not necessarily mapped to any `Company Profile`
<u>Bad</u>
- Mandatory validation on `Phone`
- Mandatory validation `Company Profile`
- `Zone` field is not necessary
- A user can be mapped to multiple positions ( many positions -> one user ) but the UI is showing only ( one user -> one position ) which is wrong
- Failed Test Cases
	- [TC-D-0005](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FUser%2FRoles%20Available%20for%20User)
	- [TC-D-0006](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FUser%2FAction%20Buttons%20against%20the%20User%20are%20not%20showing)
	- [TC-D-0007](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FUser%2FSelection%20of%20Modules%20for%20Users%20not%20Saving)
<u>Suggestions</u>
- `payments` module as a selection item is not needed. when `invoicing` module is selected, a mandatory `Payment Settings` section need to be filled which right now is sitting in `System Configuration` (Reference: Case 2)
- `Company Profile` dependencies. 
	- `Module Selection` section to show [Invoicing, Payments, Timesheets] if Company Profile is tagged `ZAP-READY`
	- `Module Selection` section to show [CMMS Retail, CMMS Vendor] if Company Profile is tagged `CMMS-READY`
	- `Module Selection` section to show [Connect] if Company Profile is tagged `CONNECT-READY`
- Employee ID to be fetched and listed in an `autocomplete` from the selected `Company Profile` -`Zap Integration`. If we use `Zap Oauth` system, we can fetch directly with the mapped email-id
# Case 8: Positions Master
### Objective:
Requires an UI to list, add, edit, deactivate Positions. As well to attach `Beats` to a specific position (many beats -> one position)
<u>Good</u>
- UI to capture [Position Name, Position Code, Level, Reports To]
<u>Bad</u>
- Missing `is_vacant`, `attached_to_employee`fields
	- While creating a Position, user either have to allocate that to a user or mark the `position` as `vacant`
- `Edit` action button navigates to `Edit Form` in which `is_active` can be unchecked/checked. `is_active` can be toggled only using `activate/deactivate` action button that involves `dependency check`
- No option to `attach_beats`. `Attach Beats` action button to be visible in `Positions list view` against each `position`
- Failed Test Cases
	- [TC-D-0008](obsidian://open?vault=software&file=Mobile%20App%201%2FReview%201%2FTest%20Cases%2FDashboard%2FPosition%2FHierarchical%20Position%20Validation)
## Case 9: Beats Master
Requires an UI to list, add, edit, deactivate 