# Import order matters: tables referenced by FKs must be defined first.
from app.models import geography        # no deps
from app.models import company          # no deps
from app.models import product_mapping  # references CompanyProfile, Product
from app.models import product          # references CompanyProfile
from app.models import vendor           # no deps (vendor before asset_cap)
from app.models import user             # defines user_positions junction; references Position, CompanyProfile
from app.models import position         # imports user_positions; references Beat via string
from app.models import beat             # imports position_beats; references Position, Outlet via string
from app.models import outlet           # references Beat, Geography
# Phase 3 — order before payment/visit (FK targets)
from app.models import order            # references Outlet, User, Beat, CompanyProfile, Product
from app.models import payment_submission  # no deps on payment (Payment references it)
from app.models import payment          # references Order, Outlet, User, PaymentSubmission
from app.models import expense          # references User
from app.models import attendance       # references User
from app.models import timesheet        # references User, Outlet, Order, Attendance
from app.models import material_request # references User, Outlet, CompanyProfile
from app.models import asset_capitalization  # references User, Outlet, CompanyProfile, Vendor
from app.models import alert            # no FK deps
from app.models import auto_flag        # references User
