---
id: TC-D-0010
priority: High
status: Failed
author: Vinod
module: Product
---
### Description
Open the "Products" Tab. We can see a list of all the products in backend. However, all the products shown are from **ZAP System** only and the **Connect System** products are not visible

Following Products also need to be fetched

```
curl --location --globoff --request GET 'http://connect.staging.sravie.in/api/resource/Connect Item?fields=[%22name%22%2C%22item_name%22%2C%22item_code%22%2C%22item_image%22%2C%22item_mrp%22]&filters={%22disabled%22%3A0}' \

--header 'Authorization: ••••••' \

--header 'Cookie: sid=Guest'
```