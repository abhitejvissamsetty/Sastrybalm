---
id: TC-D-0009
priority: High
status: Failed
author: Vinod
module: Product
---
### Description
Open the "Products" Tab. We first need "Choose Company Profile" option before showing a list of "Products". We can see a list of all the products in backend. However this *all list* is not contextual and dumping all the **Products** from backend without proper filtering

filters = [["Item Default","company","=","{{zap_company}}"], ["has_variants","=",0], ["item_group","=","Products"],["disabled","=",0]]

Need to be applied

```
curl --location --globoff --request GET 'zap.staging.sravie.in/api/resource/Item?fields=[%22*%22]&filters=[[%22Item%20Default%22%2C%22company%22%2C%22%3D%22%2C%22Sravi%20Enterprises%20-%20Kolapakkam%22]%2C%20[%22has_variants%22%2C%22%3D%22%2C0]%2C%20[%22item_group%22%2C%22%3D%22%2C%22Products%22]%2C[%22disabled%22%2C%22%3D%22%2C0]]' \

--header 'Authorization: ••••••'
```
