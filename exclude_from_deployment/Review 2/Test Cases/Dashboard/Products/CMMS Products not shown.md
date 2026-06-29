---
id: TC-D-0011
priority: High
status: Failed
author: Vinod
module: Product
---
### Description
Open the "Products" Tab. We can see a list of all the products in backend. However, all the products shown are from **ZAP System** only and the **CMMS System** products are not visible

There are 3 types of "Products" available in CMMS
1.  Asset type Items
2.  Stocked Items
3.  Service Items

#### 1. Asset Type Items needs to be fetched
```
curl --location --globoff --request GET 'http://cmms.staging.sravie.in/api/resource/Item?fields=[%22*%22]&filters=[[%22item_group%22%2C%22%3D%22%2C%22Consumable%22]%2C[%22is_fixed_asset%22%2C%22%3D%22%2C1]%2C[%22is_stock_item%22%2C%22%3D%22%2C0]%2C[%22disabled%22%2C%22%3D%22%2C0]]' \
--header 'Content-Type: application/json' \
--header 'Authorization: token 7321b107d07c80f:42a38cf6f4a3e38' \
--header 'Cookie: sid=Guest'
```
#### 2. Stocked Items needs to be fetched
```
curl --location --globoff --request GET 'http://cmms.staging.sravie.in/api/resource/Item?fields=[%22*%22]&filters=[[%22item_group%22%2C%22%3D%22%2C%22Consumable%22]%2C[%22is_fixed_asset%22%2C%22%3D%22%2C0]%2C[%22is_stock_item%22%2C%22%3D%22%2C1]%2C[%22maintain_stock%22%2C%22%3D%22%2C1]%2C[%22disabled%22%2C%22%3D%22%2C0]]' \
--header 'Content-Type: application/json' \
--header 'Authorization: token 7321b107d07c80f:42a38cf6f4a3e38' \
--header 'Cookie: sid=Guest'
```
#### 3. Service type Items need to be fetched

```
curl --location --globoff --request GET 'http://cmms.staging.sravie.in/api/resource/Item?fields=[%22*%22]&filters=[[%22item_group%22%2C%22%3D%22%2C%22Consumable%22]%2C[%22is_fixed_asset%22%2C%22%3D%22%2C0]%2C[%22is_stock_item%22%2C%22%3D%22%2C0]%2C[%22disabled%22%2C%22%3D%22%2C0]]' \
--header 'Content-Type: application/json' \
--header 'Authorization: token 7321b107d07c80f:42a38cf6f4a3e38' \
--header 'Cookie: sid=Guest'
```