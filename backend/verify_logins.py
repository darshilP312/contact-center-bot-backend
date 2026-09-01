import httpx

USERS = [
    ("anita.desai@example.com", "AnitaPass123!"),
    ("rajan.mehta@example.com", "RajanPass123!"),
    ("suresh.kumar@example.com", "SureshPass123!"),
    ("kavitha.nair@example.com", "KavithaPass123!"),
    ("priya.sharma@example.com", "PriyaPass123!"),
    ("amit.patel@email.com", "AmitPass123!"),
    ("priya.nair@email.com", "PriyaPass123!"),
    ("rahul.sharma@email.com", "RahulPass123!"),
    ("sneha.reddy@email.com", "SnehaPass123!"),
    ("vikram.singh@email.com", "VikramPass123!"),
]

with httpx.Client(timeout=30.0) as client:
    for email, pwd in USERS:
        resp = client.post("http://localhost:8000/api/v1/auth/login", json={"email": email, "password": pwd})
        print(f"[{resp.status_code}] {email} -> {'OK' if resp.status_code == 200 else resp.text}")
