"""Creates realistic fictional data so a new installation is immediately usable."""
from .database import init_db,db
from .services import upsert_company

DEMO=[
{"legal_name":"Northstar Components Ltd.","country":"CA","industry":"Manufacturing","website":"https://northstar-components.example","phone":"+1 416 555 0142","phone_type":"Main office","phone_source":"Demo data","phone_verified_at":"2026-09-16","contact_name":"Avery Chen","contact_role":"VP Operations","revenue_growth":7.2,"margin_change":-4.1,"expense_growth":15.8,"recent_acquisition":1,"management_change":1,"efficiency_mentions":5,"cost_mentions":4,"employee_count":1800,"revenue":420000000,"source_url":"https://northstar-components.example/report"},
{"legal_name":"Great Lakes Food Group, Inc.","country":"US","industry":"Food & Beverage","website":"https://greatlakes-food.example","phone":"+1 312 555 0188","phone_type":"Main office","phone_source":"Demo data","phone_verified_at":"2026-09-16","contact_role":"COO","revenue_growth":3.0,"margin_change":-3.2,"expense_growth":12.5,"restructuring":1,"efficiency_mentions":4,"cost_mentions":6,"employee_count":3200,"revenue":760000000},
{"legal_name":"Maple Route Logistics Corp.","country":"CA","industry":"Logistics","website":"https://mapleroute-logistics.example","phone":"+1 905 555 0117","phone_type":"Main office","phone_source":"Demo data","phone_verified_at":"2026-09-16","contact_name":"Morgan Patel","contact_role":"President","revenue_growth":19.0,"margin_change":-1.8,"expense_growth":25.0,"recent_acquisition":1,"efficiency_mentions":3,"cost_mentions":2,"employee_count":650,"revenue":115000000},
{"legal_name":"Cascade Health Systems, Inc.","country":"US","industry":"Healthcare","website":"https://cascade-health.example","phone":"+1 206 555 0199","phone_type":"Main office","phone_source":"Demo data","phone_verified_at":"2026-09-16","contact_role":"Chief Transformation Officer","revenue_growth":9.0,"margin_change":-2.0,"expense_growth":15.0,"restructuring":1,"management_change":1,"efficiency_mentions":6,"cost_mentions":1,"employee_count":5200,"revenue":920000000},
{"legal_name":"Prairie Build Partners Ltd.","country":"CA","industry":"Construction","website":"https://prairie-build.example","contact_role":"VP Operations","revenue_growth":5.0,"margin_change":-.5,"expense_growth":6.0,"efficiency_mentions":1,"cost_mentions":1,"employee_count":90,"revenue":18000000},
{"legal_name":"Summit Software Holdings, Inc.","country":"US","industry":"Technology","website":"https://summit-software.example","phone":"+1 415 555 0166","phone_type":"Main office","phone_source":"Demo data","phone_verified_at":"2026-09-16","contact_role":"COO","revenue_growth":28.0,"margin_change":1.2,"expense_growth":24.0,"recent_acquisition":1,"efficiency_mentions":2,"cost_mentions":0,"employee_count":800,"revenue":155000000}
]

def seed():
    init_db()
    with db() as con: count=con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    if count==0:
        for company in DEMO: upsert_company(company)

if __name__=="__main__": seed()
