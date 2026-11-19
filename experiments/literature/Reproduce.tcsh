#!/bin/tcsh -ef
# Cabbage reproduction: run from the checkout, with an unused results directory.
# Arguments: output directory and the exact CDS TSV snapshot (or download below).
if ( $#argv < 1 ) then
  echo "Usage: tcsh -ef experiments/literature/Reproduce.tcsh NEW_OUTPUT [CDS_TSV]"
  exit 2
endif
set tree = "$cwd"
set scratch = "/home/pnord/scratch"
setenv PHOEBE_STUDY_SCRATCH "$scratch"
set out = "$argv[1]"
mkdir -p "$out"
set out = `realpath "$out"`
setenv PHOEBE_STUDY_OUT "$out"
setenv OPENBLAS_NUM_THREADS 1
setenv OMP_NUM_THREADS 1
setenv MKL_NUM_THREADS 1
setenv PYTHONDONTWRITEBYTECODE 1
set py = "$scratch/phoebe-python314-20261117/check-env/bin/python"
if ( ! -e "$out/cds.tsv" ) then
  if ( $#argv == 2 ) then
    cp "$argv[2]" "$out/cds.tsv"
  else
    curl -fLsS 'https://vizier.cfa.harvard.edu/viz-bin/asu-tsv?-source=V/152/debcat&-out.all&-out.max=unlimited' -o "$out/cds.tsv"
  endif
endif
cd "$tree/experiments/literature"
$py design.py
$py supplement.py
$py extend.py
$py archive.py
$py table.py
/usr/bin/nice -n 15 taskset -c 11 node baseline.mjs "$out"
node slice_base.mjs "$out"
# This scheduler uses the previously authorized fifth42 freeze/thaw on cabbage.
# Each invocation resumes from per-curve files. No service is restarted.
$py schedule.py pilot 4 16
$py schedule.py wide 12 120
/usr/bin/nice -n 18 taskset -c 11 $py fit_wide.py --initial
$py schedule.py surface 12 48
/usr/bin/nice -n 18 taskset -c 11 $py fit_surface.py surface
$py schedule.py enrich 12 120
/usr/bin/nice -n 18 taskset -c 11 $py fit_wide.py
/usr/bin/nice -n 18 taskset -c 11 $py evaluate_wide.py
$py schedule.py eccentric 8 24
/usr/bin/nice -n 18 taskset -c 11 $py fit_surface.py eccentric
$py schedule.py mixed 12 36
/usr/bin/nice -n 18 taskset -c 11 $py fit_mixed.py --initial
$py schedule.py resolution 8 8
$py paired_extension.py
$py archive.py
$py schedule.py paired-extension 12 36
$py schedule.py audit 10 30
/usr/bin/nice -n 18 taskset -c 11 $py fit_mixed.py
$py export.py
$py inventory.py
$py figures.py
$py build_demo.py
$py wide_demo.py
set bp = "$scratch/phoebe-surrogate-results-20261118/browser-env/bin/python"
setenv PLAYWRIGHT_BROWSERS_PATH "$scratch/phoebe-surrogate-results-20261118/browsers"
# A fresh loopback port keeps the current local lab available.
set port = 8786
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$out/demo" >& "$out/http.log" &
set server = $!
$bp "$tree/tests/surface_preview_browser.py" "http://127.0.0.1:${port}/"
$bp wide_browser.py "http://127.0.0.1:${port}/study/study.html"
$bp browser.py "http://127.0.0.1:${port}/"
kill "$server"
$py report.py
cd "$tree"
/usr/bin/nice -n 18 taskset -c 11 $py -m unittest discover -s tests
