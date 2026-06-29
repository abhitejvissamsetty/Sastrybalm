---
id: TC-D-0013
priority: High
author: Vinod
status: Failed
module: Product
---
### Description
Open the "Products" Tab. We first need "Choose Company Profile" option before showing a list of "Products". After Choosing `Company Profile`, we shall query the respective `ZAP, CONNECT, CMMS` endpoints configured. We will fetch the `Products` and display them. However, the `Products` we use in `Mobile App` is not just dump of these `Products`. Example, 
1. "Sastry Balm 12.6 ML" - This Item is configured as "SASB-12.6 ML" in "ZAP" and "Sastry Balm - 12.6 ML" in "Connect" with a conversion factor of `1`
2. "Sastry Balm - 1.7 ML" - This Item is configured as "SASB-1.7 ML" in "ZAP" and "Sastry Balm - 1.7 ML Strip of 20" in "Connect" with a conversion factor of `1/20`

