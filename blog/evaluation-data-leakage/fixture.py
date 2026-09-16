"""Synthetic support cases: no customer data or model-generated outputs."""

CASES = [
    ("billing", "The invoice includes a charge for a canceled workspace."),
    ("billing", "Our payment was processed twice for the same subscription."),
    ("billing", "Please update the billing address on our next invoice."),
    ("billing", "The prepaid credits did not appear after payment."),
    ("billing", "We need a receipt for the annual subscription."),
    ("access", "My invitation expired before I joined the team."),
    ("access", "The password reset link returns an invalid token."),
    ("access", "Our new engineer cannot access the project."),
    ("access", "I replaced my phone and cannot complete two factor login."),
    ("access", "The service account is missing permission to read artifacts."),
    ("incident", "The training job stopped responding after startup."),
    ("incident", "Uploads fail with a server error in the workspace."),
    ("incident", "The prediction endpoint times out for every request."),
    ("incident", "The worker crashes while loading the model checkpoint."),
    ("incident", "The dashboard returns an error when opening run logs."),
]


def make_rows():
    rows = []
    for number, (label, text) in enumerate(CASES, start=1):
        case_id = f"case-{number:02d}"
        # Two normalized copies and one related view of the same case.
        for view, value in enumerate((text, "  " + text.upper() + "  ", "Support request: " + text)):
            rows.append({"id": f"{case_id}-{view}", "case_id": case_id,
                         "text": value, "label": label})
    # A reimport with a new case identifier; case-only grouping misses it.
    rows.append({"id": "reimport-01", "case_id": "case-99",
                 "text": CASES[0][1], "label": CASES[0][0]})
    return rows
