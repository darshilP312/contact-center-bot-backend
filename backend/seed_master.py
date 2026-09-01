"""
seed_master.py — Comprehensive Database Initializer & Seeder for InsureAI Contact Center 3.0.

Populates:
1. All DB schema tables (Base.metadata.create_all + fixing conversation_state)
2. 10 Policyholders with unique login credentials (matching AuthPage.tsx)
3. Accounts for all policyholders
4. Billing Plans, Invoices & Billing Transactions
5. Service Types, Agents, & Appointments
6. Billing Alerts
"""
import asyncio
import os
import uuid
from datetime import date, datetime, timedelta, timezone, time
from decimal import Decimal

from sqlalchemy import select, text
from app.database.session import async_session_factory, engine, Base
import app.models  # load all SQLAlchemy models
from app.models.customer import Customer, Account
from app.models.billing import BillingPlan, Invoice, BillingTransaction, BillingAlert
from app.models.scheduling import ServiceType, Agent, Appointment, AgentAvailabilityBlock
from app.core.security import get_password_hash

# --- 1. Policyholders Data ----------------------------------------------------
CUSTOMERS_DATA = [
    {
        "name": "Anita Desai",
        "email": "anita.desai@example.com",
        "password": "AnitaPass123!",
        "phone": "+91-9988776655",
        "account_number": "ACC-003",
        "plan": "Home Protector Elite",
        "tier": "premium",
        "city": "Mumbai",
        "state": "Maharashtra",
        "address": "402, Sea Green Apts, Worli",
        "pincode": "400018",
        "customer_since": date(2021, 3, 15),
    },
    {
        "name": "Rajan Mehta",
        "email": "rajan.mehta@example.com",
        "password": "RajanPass123!",
        "phone": "+91-9812345678",
        "account_number": "ACC-002",
        "plan": "Health Shield Premium",
        "tier": "premium",
        "city": "Bangalore",
        "state": "Karnataka",
        "address": "78, 4th Main, Indiranagar",
        "pincode": "560038",
        "customer_since": date(2019, 11, 20),
    },
    {
        "name": "Suresh Kumar",
        "email": "suresh.kumar@example.com",
        "password": "SureshPass123!",
        "phone": "+91-9001234567",
        "account_number": "ACC-004",
        "plan": "Motor Third Party",
        "tier": "basic",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "address": "12, Anna Nagar West",
        "pincode": "600040",
        "customer_since": date(2022, 1, 10),
    },
    {
        "name": "Kavitha Nair",
        "email": "kavitha.nair@example.com",
        "password": "KavithaPass123!",
        "phone": "+91-9876001234",
        "account_number": "ACC-005",
        "plan": "Health Shield Gold",
        "tier": "gold",
        "city": "Kochi",
        "state": "Kerala",
        "address": "25/110, Panampilly Nagar",
        "pincode": "682036",
        "customer_since": date(2020, 5, 5),
    },
    {
        "name": "Priya Sharma",
        "email": "priya.sharma@example.com",
        "password": "PriyaPass123!",
        "phone": "+91-9876543210",
        "account_number": "ACC-001",
        "plan": "Health Shield Gold",
        "tier": "gold",
        "city": "Delhi",
        "state": "Delhi",
        "address": "B-4/12, Vasant Vihar",
        "pincode": "110057",
        "customer_since": date(2020, 7, 1),
    },
    {
        "name": "Amit Patel",
        "email": "amit.patel@email.com",
        "password": "AmitPass123!",
        "phone": "+91-9823456781",
        "account_number": "ACC-006",
        "plan": "Health Shield Basic",
        "tier": "basic",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "address": "501, Shivalik Heights, Bodakdev",
        "pincode": "380054",
        "customer_since": date(2023, 2, 28),
    },
    {
        "name": "Priya Nair",
        "email": "priya.nair@email.com",
        "password": "PriyaPass123!",
        "phone": "+91-9834567892",
        "account_number": "ACC-007",
        "plan": "Motor Comprehensive",
        "tier": "gold",
        "city": "Kochi",
        "state": "Kerala",
        "address": "14/890, Marine Drive",
        "pincode": "682031",
        "customer_since": date(2021, 8, 14),
    },
    {
        "name": "Rahul Sharma",
        "email": "rahul.sharma@email.com",
        "password": "RahulPass123!",
        "phone": "+91-9845678903",
        "account_number": "ACC-008",
        "plan": "Home Protector Basic",
        "tier": "basic",
        "city": "Pune",
        "state": "Maharashtra",
        "address": "304, Green Acres, Baner",
        "pincode": "411045",
        "customer_since": date(2022, 4, 1),
    },
    {
        "name": "Sneha Reddy",
        "email": "sneha.reddy@email.com",
        "password": "SnehaPass123!",
        "phone": "+91-9856789014",
        "account_number": "ACC-009",
        "plan": "Motor Comprehensive Plus",
        "tier": "basic",
        "city": "Hyderabad",
        "state": "Telangana",
        "address": "8-2-293, Road No 14, Banjara Hills",
        "pincode": "500034",
        "customer_since": date(2023, 6, 15),
    },
    {
        "name": "Vikram Singh",
        "email": "vikram.singh@email.com",
        "password": "VikramPass123!",
        "phone": "+91-9867890125",
        "account_number": "ACC-010",
        "plan": "Motor Comprehensive",
        "tier": "gold",
        "city": "Jaipur",
        "state": "Rajasthan",
        "address": "102, Civil Lines",
        "pincode": "302006",
        "customer_since": date(2021, 12, 1),
    },
]

# --- Plan pricing table -------------------------------------------------------
PLAN_PRICES = {
    "Health Shield Basic": 3999.0,
    "Health Shield Gold": 7499.0,
    "Health Shield Premium": 14999.0,
    "Motor Comprehensive": 8999.0,
    "Motor Third Party": 2499.0,
    "Motor Comprehensive Plus": 11999.0,
    "Home Protector Basic": 4999.0,
    "Home Protector Elite": 8499.0,
}

# --- Service Types ------------------------------------------------------------
SERVICE_TYPES = [
    {
        "code": "CLAIM_SURVEY",
        "name": "On-site Claim Damage Inspection",
        "description": "Physical inspection of motor or home property by surveyor",
        "category": "claims",
        "domain": "insurance",
        "estimated_duration_mins": 45,
        "priority_weight": 8,
    },
    {
        "code": "POLICY_RENEWAL",
        "name": "Policy Renewal & Plan Upgrade Consultation",
        "description": "Discuss policy renewals, discounts, and NCB carry-forward",
        "category": "policy",
        "domain": "insurance",
        "estimated_duration_mins": 30,
        "priority_weight": 5,
    },
    {
        "code": "BILLING_DISPUTE",
        "name": "Billing & Premium Discrepancy Review",
        "description": "Review erroneous charge, tax recalculation or refund review",
        "category": "billing",
        "domain": "insurance",
        "estimated_duration_mins": 30,
        "priority_weight": 7,
    },
    {
        "code": "GENERAL_SUPPORT",
        "name": "General Insurance Advisor Call",
        "description": "Comprehensive advisory on health, motor, and home covers",
        "category": "advisory",
        "domain": "insurance",
        "estimated_duration_mins": 20,
        "priority_weight": 4,
    },
]

# --- Human Agents -------------------------------------------------------------
AGENTS = [
    {
        "agent_code": "AGT-101",
        "name": "Rohan Sharma",
        "email": "rohan.sharma@insureai.com",
        "phone": "+91-9871000001",
        "role": "senior_surveyor",
        "department": "claims",
        "specializations": ["motor_claims", "home_claims"],
        "languages": ["en", "hi"],
    },
    {
        "agent_code": "AGT-102",
        "name": "Ananya Sen",
        "email": "ananya.sen@insureai.com",
        "phone": "+91-9871000002",
        "role": "policy_specialist",
        "department": "policy",
        "specializations": ["health_insurance", "tax_benefits"],
        "languages": ["en", "hi", "bn"],
    },
    {
        "agent_code": "AGT-103",
        "name": "Deepak Verma",
        "email": "deepak.verma@insureai.com",
        "phone": "+91-9871000003",
        "role": "billing_supervisor",
        "department": "billing",
        "specializations": ["refunds", "disputes", "gst"],
        "languages": ["en", "hi"],
    },
]


async def seed_master():
    print("==================================================")
    print(">> Starting Master Database Seeder")
    print("==================================================")

    # 1. Fix schema / conversation_state compatibility
    async with engine.begin() as conn:
        # Check if conversation_state exists without conversation_id
        check_col = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='conversation_state' AND column_name='conversation_id'"
        ))
        if not check_col.scalar():
            print("[INFO] Fixing conversation_state schema table...")
            await conn.execute(text("DROP TABLE IF EXISTS conversation_state CASCADE;"))

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        print("[OK] Database tables created/verified")

    today = date.today()
    now_utc = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        # 2. Seed Billing Plans
        print("\n--- Seeding Billing Plans ---")
        for plan_name, base_price in PLAN_PRICES.items():
            plan_code = plan_name.upper().replace(" ", "_")
            existing_plan = (await db.execute(select(BillingPlan).where(BillingPlan.name == plan_name))).scalar_one_or_none()
            if not existing_plan:
                plan_obj = BillingPlan(
                    plan_code=plan_code,
                    name=plan_name,
                    description=f"{plan_name} quarterly insurance policy cover",
                    category="insurance",
                    base_amount=Decimal(str(base_price)),
                    billing_cycle="quarterly",
                    currency="INR",
                    tax_rate_pct=Decimal("18.00"),
                    is_active=True,
                )
                db.add(plan_obj)
                print(f"  + Billing Plan: {plan_name} (Rs.{base_price})")
        await db.flush()

        # 3. Seed Service Types & Agents
        print("\n--- Seeding Service Types & Agents ---")
        st_map = {}
        for st in SERVICE_TYPES:
            existing_st = (await db.execute(select(ServiceType).where(ServiceType.code == st["code"]))).scalar_one_or_none()
            if not existing_st:
                st_obj = ServiceType(**st)
                db.add(st_obj)
                await db.flush()
                st_map[st["code"]] = st_obj
                print(f"  + Service Type: {st['name']}")
            else:
                st_map[st["code"]] = existing_st

        agent_objs = []
        for ag in AGENTS:
            existing_ag = (await db.execute(select(Agent).where(Agent.agent_code == ag["agent_code"]))).scalar_one_or_none()
            if not existing_ag:
                ag_obj = Agent(**ag)
                db.add(ag_obj)
                await db.flush()
                agent_objs.append(ag_obj)
                print(f"  + Agent: {ag['name']} ({ag['agent_code']})")
            else:
                agent_objs.append(existing_ag)

        # 4. Seed Customers & Accounts
        print("\n--- Seeding Policyholders & Logins ---")
        seeded_customers = []
        for cdata in CUSTOMERS_DATA:
            existing = (await db.execute(select(Customer).where(Customer.email == cdata["email"]))).scalar_one_or_none()
            pass_hash = get_password_hash(cdata["password"])

            if not existing:
                cid = uuid.uuid4()
                cust = Customer(
                    customer_id=cid,
                    name=cdata["name"],
                    email=cdata["email"],
                    phone=cdata["phone"],
                    account_number=cdata["account_number"],
                    plan=cdata["plan"],
                    password_hash=pass_hash,
                    is_active=True,
                    customer_tier=cdata["tier"],
                    city=cdata["city"],
                    state=cdata["state"],
                    address_line1=cdata["address"],
                    pincode=cdata["pincode"],
                    customer_since=cdata["customer_since"],
                    preferred_language="en",
                    preferred_channel="voice",
                )
                db.add(cust)
                await db.flush()

                # Add Account
                acct = Account(
                    customer_id=cid,
                    plan_name=cdata["plan"],
                    balance=0.0,
                    status="active",
                    billing_cycle="quarterly",
                    payment_method="UPI",
                )
                db.add(acct)
                await db.flush()

                seeded_customers.append((cust, acct, cdata))
                print(f"  + Customer: {cdata['name']} ({cdata['email']}) -> Password: {cdata['password']}")
            else:
                existing.password_hash = pass_hash
                existing.is_active = True
                db.add(existing)
                # Fetch account
                acct = (await db.execute(select(Account).where(Account.customer_id == existing.customer_id))).scalar_one_or_none()
                if not acct:
                    acct = Account(
                        customer_id=existing.customer_id,
                        plan_name=existing.plan or cdata["plan"],
                        balance=0.0,
                        status="active",
                        billing_cycle="quarterly",
                        payment_method="UPI",
                    )
                    db.add(acct)
                    await db.flush()
                seeded_customers.append((existing, acct, cdata))
                print(f"  ~ Updated Password: {cdata['name']} ({cdata['email']})")

        await db.flush()

        # 5. Seed Invoices & Transactions
        print("\n--- Seeding Invoices & Transactions ---")
        inv_idx = 100
        for cust, acct, cdata in seeded_customers:
            plan_name = cdata["plan"]
            base_amt = Decimal(str(PLAN_PRICES.get(plan_name, 4999.0)))
            gst = (base_amt * Decimal("0.18")).quantize(Decimal("0.01"))
            total = base_amt + gst

            # Check existing invoices
            existing_invs = (await db.execute(select(Invoice).where(Invoice.customer_id == cust.customer_id))).scalars().all()
            if not existing_invs:
                # 1. Paid invoice (2 months ago)
                inv_idx += 1
                p_start = (today.replace(day=1) - timedelta(days=60)).replace(day=1)
                p_end = p_start + timedelta(days=89)
                inv_paid = Invoice(
                    customer_id=cust.customer_id,
                    account_id=acct.account_id,
                    invoice_number=f"INV-2026-{inv_idx:04d}",
                    status="paid",
                    billing_period_start=p_start,
                    billing_period_end=p_end,
                    due_date=p_start + timedelta(days=15),
                    issue_date=p_start,
                    subtotal=base_amt,
                    taxable_amount=base_amt,
                    cgst_amount=gst / 2,
                    sgst_amount=gst / 2,
                    tax_amount=gst,
                    total_amount=total,
                    amount_paid=total,
                    currency="INR",
                    line_items=[{"description": f"{plan_name} Quarterly Premium", "amount": float(base_amt)}],
                    paid_at=now_utc - timedelta(days=45),
                    sent_via="email",
                    sent_at=now_utc - timedelta(days=60),
                )
                db.add(inv_paid)
                await db.flush()

                # Paid transaction
                txn_paid = BillingTransaction(
                    customer_id=cust.customer_id,
                    account_id=acct.account_id,
                    invoice_id=inv_paid.invoice_id,
                    transaction_type="payment",
                    amount=total,
                    currency="INR",
                    status="success",
                    payment_method="upi",
                    upi_txn_id=f"UPI-{uuid.uuid4().hex[:10].upper()}",
                    net_amount=total,
                )
                db.add(txn_paid)

                # 2. Current invoice (issued, pending/unpaid)
                inv_idx += 1
                c_start = today.replace(day=1)
                c_end = c_start + timedelta(days=89)
                inv_curr = Invoice(
                    customer_id=cust.customer_id,
                    account_id=acct.account_id,
                    invoice_number=f"INV-2026-{inv_idx:04d}",
                    status="unpaid" if cdata["tier"] != "premium" else "paid",
                    billing_period_start=c_start,
                    billing_period_end=c_end,
                    due_date=c_start + timedelta(days=20),
                    issue_date=c_start,
                    subtotal=base_amt,
                    taxable_amount=base_amt,
                    cgst_amount=gst / 2,
                    sgst_amount=gst / 2,
                    tax_amount=gst,
                    total_amount=total,
                    amount_paid=total if cdata["tier"] == "premium" else Decimal("0.00"),
                    currency="INR",
                    line_items=[{"description": f"{plan_name} Quarterly Renewal Premium", "amount": float(base_amt)}],
                    sent_via="email",
                    sent_at=now_utc - timedelta(days=2),
                )
                db.add(inv_curr)

                # Billing Alert
                alert = BillingAlert(
                    customer_id=cust.customer_id,
                    alert_type="invoice_issued",
                    severity="info",
                    title="Quarterly Policy Premium Due",
                    message=f"Your {plan_name} premium of Rs.{total} is generated.",
                    is_read=False,
                )
                db.add(alert)
                print(f"  + Invoices generated for: {cust.name}")

        # 6. Seed Appointments
        print("\n--- Seeding Sample Appointments ---")
        if agent_objs and st_map:
            st_claim = st_map.get("CLAIM_SURVEY")
            st_renew = st_map.get("POLICY_RENEWAL")
            agent_rohan = agent_objs[0]

            for i, (cust, acct, cdata) in enumerate(seeded_customers[:3]):
                existing_apt = (await db.execute(select(Appointment).where(Appointment.customer_id == cust.customer_id))).scalar_one_or_none()
                if not existing_apt:
                    sched_time = now_utc + timedelta(days=2 + i, hours=i * 2)
                    apt = Appointment(
                        appointment_number=f"APT-2026-{(i+1):04d}",
                        customer_id=cust.customer_id,
                        account_id=acct.account_id,
                        agent_id=agent_rohan.agent_id,
                        service_type_id=st_claim.service_type_id if i == 0 else st_renew.service_type_id,
                        scheduled_at=sched_time,
                        window_start=sched_time,
                        window_end=sched_time + timedelta(minutes=45),
                        duration_mins=45,
                        channel="on_site" if i == 0 else "voice_call",
                        status="scheduled",
                        reason="Inspection of policy incident" if i == 0 else "Annual policy coverage consultation",
                        reason_detail=f"Automated briefing for {cust.name} ({cust.plan})",
                        intent_category="claims" if i == 0 else "policy",
                    )
                    db.add(apt)
                    print(f"  + Appointment: {apt.appointment_number} for {cust.name}")

        await db.commit()
        print("\n==================================================")
        print("[SUCCESS] Master Seeding Complete!")
        print("==================================================")


if __name__ == "__main__":
    os.environ["PYTHONPATH"] = os.getcwd()
    asyncio.run(seed_master())
