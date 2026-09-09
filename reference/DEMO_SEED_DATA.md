# Demo Seed Data

Create synthetic files:

demo_data/
├── confidential_customer_data.csv
├── employee_records.csv
├── ordinary_document.txt
├── recoverable_project_notes.md
├── temp/
│   ├── office_autosave.tmp
│   └── customer_export.tmp
└── nested/
    └── archive/
        └── confidential_report.txt

Expected:
- confidential_customer_data.csv → CRITICAL
- employee_records.csv → CRITICAL
- ordinary_document.txt → INTERNAL
- recoverable_project_notes.md → CONFIDENTIAL

All identities, numbers and addresses must be synthetic.
