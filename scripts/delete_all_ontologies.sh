#!/bin/bash
# Delete all ontologies - clean slate for testing new architecture
# Created for feature/vocabulary-based-appears branch
# This deletes all data - only use when intentionally resetting!

set -e

echo "🗑️  Deleting all ontologies from knowledge graph..."
echo ""

# All 66 ontologies (entire Bible)
ontologies=(
  "01_Genesis"
  "02_Exodus"
  "03_Leviticus"
  "04_Numbers"
  "05_Deuteronomy"
  "06_Joshua"
  "07_Judges"
  "08_Ruth"
  "09_I_Samuel"
  "10_II_Samuel"
  "11_I_Kings"
  "12_II_Kings"
  "13_I_Chronicles"
  "14_II_Chronicles"
  "15_Ezra"
  "16_Nehemiah"
  "17_Esther"
  "18_Job"
  "19_Psalms"
  "20_Proverbs"
  "21_Ecclesiastes"
  "22_Song_of_Solomon"
  "23_Isaiah"
  "24_Jeremiah"
  "25_Lamentations"
  "26_Ezekiel"
  "27_Daniel"
  "28_Hosea"
  "29_Joel"
  "30_Amos"
  "31_Obadiah"
  "32_Jonah"
  "33_Micah"
  "34_Nahum"
  "35_Habakkuk"
  "36_Zephaniah"
  "37_Haggai"
  "38_Zechariah"
  "39_Malachi"
  "40_Matthew"
  "41_Mark"
  "42_Luke"
  "43_John"
  "44_Acts"
  "45_Romans"
  "46_I_Corinthians"
  "47_II_Corinthians"
  "48_Galatians"
  "49_Ephesians"
  "50_Philippians"
  "51_Colossians"
  "52_I_Thessalonians"
  "53_II_Thessalonians"
  "54_I_Timothy"
  "55_II_Timothy"
  "56_Titus"
  "57_Philemon"
  "58_Hebrews"
  "59_James"
  "60_I_Peter"
  "61_II_Peter"
  "62_I_John"
  "63_II_John"
  "64_III_John"
  "65_Jude"
  "66_Revelation_of_John"
)

total=${#ontologies[@]}
count=0

for ontology in "${ontologies[@]}"; do
  count=$((count + 1))
  echo "[$count/$total] Deleting: $ontology"
  kg ontology delete "$ontology" --force
done

echo ""
echo "✓ All ontologies deleted"
echo ""
echo "Next steps:"
echo "  • Verify: kg ontology list"
echo "  • Verify: kg database stats"
echo "  • Re-ingest with new architecture: kg ingest file -o \"01_Genesis\" <file>"
