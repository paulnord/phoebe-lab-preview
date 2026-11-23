"""Build the semi-detached training/validation notebook from the frozen model."""
from pathlib import Path
import json, nbformat as nbf
ROOT=Path(__file__).resolve().parents[1];MODEL=json.loads((ROOT/"site/experiment/semi-model.json").read_text())
nb=nbf.v4.new_notebook();nb["metadata"]={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python","version":"3"},"colab":{"name":"PHOEBE Semi-Detached Validation.ipynb","provenance":[]}}
c=[]
c.append(nbf.v4.new_markdown_cell("""# PHOEBE Semi-Detached Preview Validation

This is the reproducibility and validation notebook for the trained semi-detached preview. For observation upload and native fitting, use `PHOEBE_Semi_Detached_Binary_Colab.ipynb`.

Native PHOEBE 2.5.4 is the fitting and export reference. The embedded donor-specific surrogate is display-only and covers circular, synchronous Johnson:V systems with one native Roche-lobe constraint.

Preview domain: inclination 65–90°, q=M₂/M₁ 0.40–1.30, free-star Roche-fill fraction 0.25–0.82, T₂/T₁ 0.76–1.14; fixed P=1.8 d, M₁=1.2 M☉, T₁=6300 K, irradiation off. Outside this domain, use `native_flux`.

Photometry can leave q degenerate, particularly in partial/grazing eclipses. RV curves are complementary evidence. The benchmark below deliberately fixes q; low residuals alone are not a uniqueness claim."""))
c.append(nbf.v4.new_code_cell("""import importlib.util, subprocess, sys
if importlib.util.find_spec("phoebe") is None:
    subprocess.check_call([sys.executable,"-m","pip","install","-q","phoebe==2.5.4","scipy","matplotlib"])
"""))
c.append(nbf.v4.new_code_cell("""import json, numpy as np, matplotlib.pyplot as plt
from scipy.optimize import least_squares
import phoebe
print("PHOEBE",phoebe.__version__)
"""))
c.append(nbf.v4.new_code_cell("SEMI_MODEL=json.loads(r'''"+json.dumps(MODEL,separators=(",",":"))+"''')"))
c.append(nbf.v4.new_code_cell("""def roche_lobe_fraction(star_mass_ratio):
    root=np.cbrt(star_mass_ratio);square=root*root
    return .49*square/(.6*square+np.log1p(root))

def semi_preview(donor="primary",inclination=84.5,mass_ratio=.75,free_fill=.55,temperature_ratio=.9,period=1.8,irradiation=False):
    s=SEMI_MODEL
    if donor not in ("primary","secondary"):raise ValueError("donor must be primary or secondary")
    if period!=s["fixed"]["period"] or irradiation:raise ValueError("Preview requires P=1.8 d and irradiation off")
    values=dict(inclination=inclination,mass_ratio=mass_ratio,free_fill=free_fill,temperature_ratio=temperature_ratio);x=[]
    for key in s["keys"]:
        lo,hi=s["bounds"][key];value=float(values[key])
        if not lo<=value<=hi:raise ValueError(f"{key} is outside {lo}–{hi}; use native_flux")
        x.append(2*(value-lo)/(hi-lo)-1)
    x=np.asarray(x);m=s["donors"][donor];centers=np.asarray(m["centers"]);dist=np.sqrt(np.sum((centers-x)**2,axis=1))
    if dist.min()>m["nearest_scaled_distance_max"]:raise ValueError("Point is too far from training systems; use native_flux")
    coeff=np.exp(-m["gamma"]*dist**2)@np.asarray(m["weights"]);phase=np.linspace(-.5,.5,s["phases"]+1);flux=np.cos(2*np.pi*np.outer(phase,np.arange(s["harmonics"]+1)))@coeff
    return phase,flux/np.median(flux[:-1])

def semi_bundle(donor,phases,triangles=800):
    b=phoebe.default_binary(semidetached=donor);b.flip_constraint("mass@primary",solve_for="sma@binary");b.set_value("mass",component="primary",value=1.2)
    b.add_dataset("lc",dataset="semi_lc",compute_phases=phases,passband="Johnson:V");b.set_value_all("ntriangles",value=triangles);return b

def native_flux(donor="primary",inclination=84.5,mass_ratio=.75,free_fill=.55,temperature_ratio=.9,period=1.8,irradiation=False,phases=None,triangles=800):
    phases=np.linspace(-.5,.5,129) if phases is None else np.asarray(phases);b=semi_bundle(donor,phases,triangles);free="secondary" if donor=="primary" else "primary"
    b.set_value("period",component="binary",value=period);b.set_value("q",component="binary",value=mass_ratio);maximum=b.get_value("requiv_max",component=free,context="component");b.set_value("requiv",component=free,context="component",value=free_fill*maximum)
    b.set_value("teff",component="primary",value=6300.);b.set_value("teff",component="secondary",value=6300.*temperature_ratio);b.set_value("incl",component="binary",value=inclination);b.set_value("irrad_method",value="horvat" if irradiation else "none")
    b.run_compute(model="semi_model",overwrite=True,progressbar=False);flux=np.asarray(b.get_value("fluxes",dataset="semi_lc",model="semi_model"));return phases,flux/np.median(flux)
"""))
c.append(nbf.v4.new_code_cell("""p,f=semi_preview(donor="primary")
plt.plot(p,f,label="primary-donor surrogate");plt.xlabel("orbital phase");plt.ylabel("median-normalized Johnson V flux");plt.legend();
"""))
c.append(nbf.v4.new_markdown_cell("""## Observations, residuals, and native export

The notebook preview runs in the kernel; controls added with ipywidgets would make a kernel round trip. Only native curves should be used for final residuals and CSV export."""))
c.append(nbf.v4.new_code_cell("""def read_observations(path):
    a=np.genfromtxt(path,delimiter=",",names=True);names=a.dtype.names
    if not names or len(names)<2:raise ValueError("CSV needs named phase and flux columns")
    phase,flux=np.asarray(a[names[0]]),np.asarray(a[names[1]])
    if len(phase)<8 or len(phase)!=len(flux) or not np.isfinite(phase).all() or not np.isfinite(flux).all():raise ValueError("Need at least 8 finite phase/flux pairs")
    return phase,flux/np.median(flux)
def compare(model_phase,model_flux,obs_phase,obs_flux):
    predicted=np.interp((obs_phase+.5)%1-.5,model_phase,model_flux);scale=np.dot(obs_flux,predicted)/np.dot(predicted,predicted);residual=obs_flux-scale*predicted;return scale*predicted,residual,float(np.sqrt(np.mean(residual**2)))
def export_native_csv(path,parameters,phases=513,triangles=1500):
    x,y=native_flux(**parameters,phases=np.linspace(-.5,.5,phases),triangles=triangles);np.savetxt(path,np.column_stack([x,y]),delimiter=",",header="phase,normalized_flux",comments="");return x,y
"""))
c.append(nbf.v4.new_markdown_cell("""## Bounded native recovery benchmark

This high-inclination example fixes donor, q, and temperature ratio, then searches only inclination and free-star fill on 65 phases. A separate 513-phase, 1,500-triangle recompute validates the result. This deliberately constrained exercise does not claim photometric q recovery.

Branch QA recovered 87.993427 degrees and free fill 0.58000846 from truth 88.0 and 0.58; the independent 513-phase native RMS was 0.00002072. Set the flag below to reproduce it (runtime depends on the Colab/Jupyter CPU)."""))
c.append(nbf.v4.new_code_cell("""RUN_NATIVE_BENCHMARK=False
if RUN_NATIVE_BENCHMARK:
    truth=dict(donor="primary",inclination=88.,mass_ratio=.75,free_fill=.58,temperature_ratio=.9,period=1.8,irradiation=False);grid=np.linspace(-.5,.5,65);_,observed=native_flux(**truth,phases=grid)
    def residual(v):return native_flux(donor=truth["donor"],inclination=v[0],mass_ratio=truth["mass_ratio"],free_fill=v[1],temperature_ratio=truth["temperature_ratio"],period=1.8,phases=grid)[1]-observed
    # Mesh calculations need physically resolvable derivative probes; SciPy's tiny defaults can look numerically flat.
    result=least_squares(residual,[86.,.52],bounds=([65,.25],[90,.82]),diff_step=np.array([.005,.02]),x_scale=np.array([2.,.1]),max_nfev=12,ftol=1e-6,xtol=1e-6,gtol=1e-6);fit=dict(donor="primary",inclination=result.x[0],mass_ratio=.75,free_fill=result.x[1],temperature_ratio=truth["temperature_ratio"],period=1.8,irradiation=False);final=np.linspace(-.5,.5,513);yt=native_flux(**truth,phases=final,triangles=1500)[1];yf=native_flux(**fit,phases=final,triangles=1500)[1]
    print("65-phase search",fit,"converged",result.success,result.message);print("513-phase native RMS",np.sqrt(np.mean((yf-yt)**2)))
"""))
c.append(nbf.v4.new_markdown_cell("""## Forward and slider-response checks

The committed report evaluates both donor choices on untouched physical systems and compares native versus surrogate **flux-difference vectors** near grazing and lobe-filling boundaries. Direction cosine and response-amplitude error are reported separately from pointwise RMS. This matters because parameters can have nearly orthogonal light-curve responses even when two absolute curves look similarly close."""))
c.append(nbf.v4.new_code_cell("""RUN_HELDOUT_FORWARD=False
CASES=[dict(donor="primary",inclination=69.,mass_ratio=.46,free_fill=.78,temperature_ratio=.8),dict(donor="secondary",inclination=87.,mass_ratio=1.2,free_fill=.8,temperature_ratio=1.1)]
if RUN_HELDOUT_FORWARD:
    for case in CASES:
        xp,yp=semi_preview(**case);xn,yn=native_flux(**case,phases=xp);print(case["donor"],"RMS",np.sqrt(np.mean((yp-yn)**2)),"max",np.max(np.abs(yp-yn)))
"""))
c.append(nbf.v4.new_markdown_cell("""## Portability and limits

- Colab: free CPU runtime is sufficient; live Colab was not used during branch QA.
- JupyterLab/classic: select a kernel with PHOEBE 2.5.4 installed.
- No disk/stream renderer, spots, eccentric semi-detached preview, or joint photometry/RV fitter is included.
- RV observations can still be inspected alongside the light curve in the standalone app and are scientifically important for mass-ratio constraints.
"""))
nb["cells"]=c;out=ROOT/"notebooks/PHOEBE_Semi_Detached_Validation.ipynb";nbf.write(nb,out);print(out)
