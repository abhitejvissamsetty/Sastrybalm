# Import order matters: tables referenced by FKs must be defined first.
from app.models import geography        # no deps
from app.models import company          # no deps
from app.models import warehouse        # no deps
from app.models import product_mapping  # references CompanyProfile, Product
from app.models import product_warehouse
from app.models import product          # references CompanyProfile, Warehouse
from app.models import vendor           # no deps (vendor before asset_cap)
from app.models import user             # defines user_positions junction; references Position, CompanyProfile
from app.models import position         # imports user_positions; references Beat via string
from app.models import beat             # imports position_beats; references Position, Outlet via string
from app.models import outlet           # references Beat, Geography
from app.models import outlet_version   # snapshots of outlet edits
from app.models import payment          # references Order, Outlet, User
from app.models import expense          # references User
from app.models import attendance       # references User
from app.models import timesheet        # references User, Outlet, Order, Attendance
from app.models import material_request # references User, Outlet, CompanyProfile
from app.models import recce            # references MaterialRequest, Vendor, User
from app.models import procurement      # references MaterialRequest, Vendor, User
from app.models import asset_capitalization  # references User, Outlet, CompanyProfile, Vendor
from app.models import alert            # no FK deps
from app.models import auto_flag        # references User
from app.models import local_distribution # native channel partners & pincode mappings
from app.models import user_otp
from app.models import beat_channel_partner
from app.models import inventory
from app.models import webhook
from app.models import beat_type
from app.models import leave
