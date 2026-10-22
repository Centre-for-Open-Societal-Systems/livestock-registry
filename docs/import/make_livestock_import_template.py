"""Build the livestock File Import template (Excel + CSV) from the code lists.

    python3 docs/import/make_livestock_import_template.py <code_list_sql> <out_dir>

<code_list_sql> is livestock-extension/.../master_data/code_lists/20_g2p_attribute_values.sql,
so the template's dropdowns always match what the registry accepts. Needs
openpyxl (the celery image has it). Writes:

  livestock_import_template.xlsx   sheet "Livestock" (headers only, the sheet
                                   that is read on import), "Allowed values",
                                   "Instructions", "Example"
  livestock_import_template.csv    the same headers, for CSV users

Rerun after a code list change and commit both files, plus the copy in
docker/staff-ui/assets/ that the portal serves.
"""

import csv
import re
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# (column, required, what it holds). Order = column order in the file.
COLUMNS = [
    ("farmer_id", "yes*", "Farmer ID, FR- followed by 10 digits (FR-0000000001). Rows with the same Farmer ID become one record with all their animals."),
    ("fayda_fan_id", "yes", "Fayda FAN ID, 16 digits, no prefix."),
    ("first_name", "yes", "Farmer's first name."),
    ("middle_name", "no", "Farmer's middle (father's) name."),
    ("last_name", "yes", "Farmer's last (grandfather's) name."),
    ("mobile_number", "no", "Farmer's mobile: 09 or 07 and 8 more digits (0911223344), or +2519 / +2517 and 8 digits."),
    ("region", "yes", "Region name, as in the portal (Oromia)."),
    ("zone", "yes", "Zone name (East Shewa)."),
    ("woreda", "yes", "Woreda name (Ada'a). Decides which Woreda approver gets the record."),
    ("kebele", "yes", "Kebele name (Dire Arerti)."),
    ("ear_tag_id", "yes**", "Ear tag, ET followed by 10 digits (ET0000000001)."),
    ("secondary_identifier", "yes**", "For species without ear tags (poultry, beehive): the flock / hive identifier."),
    ("species", "yes", "Species code, pick from the list."),
    ("breed", "yes", "Breed code of that species, pick from the list (see Allowed values for which breed belongs to which species)."),
    ("gender", "yes", "MALE or FEMALE; MIXED only for a flock / hive."),
    ("date_of_birth", "yes***", "YYYY-MM-DD, not in the future."),
    ("weight", "no", "Kilograms, more than 0."),
    ("colour", "no", "Coat colour, free text."),
    ("quantity", "yes***", "Number of birds / hives, for a flock or hive species."),
    ("health_status", "yes", "Pick from the list."),
    ("vaccination_status", "yes", "Pick from the list."),
    ("registration_date", "no", "YYYY-MM-DD, not before the date of birth; empty = today."),
]
NOTES = [
    "*   Farmer ID or Fayda FAN ID groups the rows of one farmer; give at least one of them on every row.",
    "**  Ear tag for ear-tagged species (cattle, sheep, goat, camel, donkey, horse, mule, pig); secondary identifier for poultry and beehives.",
    "*** Date of birth for individual animals; quantity for a flock or hive.",
]
GENDER = ["MALE", "FEMALE", "MIXED"]
HEALTH = ["HEALTHY", "SICK", "QUARANTINED", "DECEASED"]
VACCINATION = ["UP_TO_DATE", "OVERDUE", "NONE"]
EXAMPLE = [
    ["FR-0000000001", "1000000000000001", "Abebe", "Kebede", "Tessema", "0911000001", "Oromia", "East Shewa", "Ada'a", "Dire Arerti",
     "ET0000000101", "", "LIVESTOCK_SPECIES_CATTLE", "LIVESTOCK_BREED_BORAN", "FEMALE", "2022-03-01", "320", "Brown", "", "HEALTHY", "UP_TO_DATE", ""],
    ["FR-0000000001", "1000000000000001", "Abebe", "Kebede", "Tessema", "0911000001", "Oromia", "East Shewa", "Ada'a", "Dire Arerti",
     "ET0000000102", "", "LIVESTOCK_SPECIES_CATTLE", "LIVESTOCK_BREED_FOGERA", "MALE", "2023-01-15", "280", "", "", "HEALTHY", "NONE", ""],
    ["FR-0000000002", "1000000000000002", "Hana", "", "Girma", "", "Oromia", "East Shewa", "Ada'a", "Dire Arerti",
     "", "FLOCK-0001", "LIVESTOCK_SPECIES_POULTRY", "LIVESTOCK_BREED_SASSO", "MIXED", "", "", "", "25", "HEALTHY", "UP_TO_DATE", ""],
]


def read_code_lists(sql_path):
    """(value_id, attribute_id, label, parent) rows from the code list seed."""
    row = re.compile(r"^\('([^']+)','([^']+)','[^']*','((?:[^']|'')*)',(NULL|'[^']*'),\d+\)")
    out = []
    for line in open(sql_path, encoding="utf-8"):
        m = row.match(line.strip())
        if m:
            parent = None if m.group(4) == "NULL" else m.group(4).strip("'")
            out.append((m.group(1), m.group(2), m.group(3).replace("''", "'"), parent))
    return out


def main(sql_path, out_dir):
    values = read_code_lists(sql_path)
    species = [(v, label) for v, a, label, _ in values if a == "LIVESTOCK_SPECIES"]
    breeds = [(v, label, parent) for v, a, label, parent in values if a == "LIVESTOCK_BREED"]
    species_label = dict(species)
    assert species and breeds, "no species / breeds read from " + sql_path

    headers = [c for c, _, _ in COLUMNS]
    wb = Workbook()
    head_font, head_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2E7D32")

    # Sheet 1: the one the import reads (the active sheet when the file is saved).
    ws = wb.active
    ws.title = "Livestock"
    ws.append(headers)
    for i, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=i)
        cell.font, cell.fill = head_font, head_fill
        ws.column_dimensions[get_column_letter(i)].width = max(14, len(h) + 4)
        # Text format, so Excel keeps leading zeros (Fayda, mobile) and dates as typed.
        for r in range(2, 2002):
            ws.cell(row=r, column=i).number_format = "@"
    ws.freeze_panes = "A2"

    # Sheet 2: allowed values, also the source of the dropdowns.
    av = wb.create_sheet("Allowed values")
    av.append(["species code", "species", "", "breed code", "breed", "breed of species", "", "gender", "", "health_status", "", "vaccination_status"])
    for c in av[1]:
        c.font = Font(bold=True)
    n = max(len(species), len(breeds), len(GENDER), len(HEALTH), len(VACCINATION))
    for i in range(n):
        s = species[i] if i < len(species) else ("", "")
        b = breeds[i] if i < len(breeds) else ("", "", None)
        av.append([s[0], s[1], "", b[0], b[1], species_label.get(b[2], b[2] or ""), "",
                   GENDER[i] if i < len(GENDER) else "", "",
                   HEALTH[i] if i < len(HEALTH) else "", "",
                   VACCINATION[i] if i < len(VACCINATION) else ""])
    for col, width in zip("ABCDEFGHIJKL", (28, 14, 2, 36, 28, 18, 2, 10, 2, 16, 2, 20)):
        av.column_dimensions[col].width = width

    def dropdown(column, source):
        idx = headers.index(column) + 1
        dv = DataValidation(type="list", formula1=source, allow_blank=True, showErrorMessage=True,
                            errorTitle="Not in the list", error=f"Pick a value from the {column} list (sheet Allowed values).")
        ws.add_data_validation(dv)
        dv.add(f"{get_column_letter(idx)}2:{get_column_letter(idx)}2001")

    dropdown("species", f"'Allowed values'!$A$2:$A${len(species) + 1}")
    dropdown("breed", f"'Allowed values'!$D$2:$D${len(breeds) + 1}")
    dropdown("gender", f"'Allowed values'!$H$2:$H${len(GENDER) + 1}")
    dropdown("health_status", f"'Allowed values'!$J$2:$J${len(HEALTH) + 1}")
    dropdown("vaccination_status", f"'Allowed values'!$L$2:$L${len(VACCINATION) + 1}")

    # Sheet 3: instructions.
    ins = wb.create_sheet("Instructions")
    ins.append(["Livestock import template"])
    ins["A1"].font = Font(bold=True, size=14)
    for line in (
        "Fill the sheet 'Livestock', one row per animal (or per flock / hive). Keep row 1 (the column names) as it is.",
        "Upload in the portal: Form Submissions > Create New Submission > Import from file > LIVESTOCK_IMPORT_V1.",
        "Rows of the same farmer become ONE Livestock record with all its animals. Each record is checked like a web entry",
        "(formats, species / breed, duplicates) and then waits for the Woreda approver of its woreda.",
        "A record that fails a check is not created; fix the row and upload the file again.",
        "Save the file with the 'Livestock' sheet selected: the import reads the sheet that is open when the file is saved.",
        "",
    ):
        ins.append([line])
    ins.append(["column", "required", "what to enter"])
    for c in ins[ins.max_row]:
        c.font = Font(bold=True)
    for col in COLUMNS:
        ins.append(list(col))
    ins.append([""])
    for note in NOTES:
        ins.append([note])
    ins.column_dimensions["A"].width = 24
    ins.column_dimensions["B"].width = 10
    ins.column_dimensions["C"].width = 120
    for row in ins.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=False, vertical="top")

    # Sheet 4: a filled example (not read on import).
    ex = wb.create_sheet("Example")
    ex.append(headers)
    for c in ex[1]:
        c.font = Font(bold=True)
    for r in EXAMPLE:
        ex.append(r)

    wb.active = 0
    wb.save(f"{out_dir}/livestock_import_template.xlsx")
    with open(f"{out_dir}/livestock_import_template.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(headers)
    print(f"template: {len(headers)} columns, {len(species)} species, {len(breeds)} breeds")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
