export const NATIVE_PROJECT_ERROR='Native PHOEBE project files are intentionally disabled in Colab. Import an observation table or PHOEBE Lab session; exact curves, fits, and surfaces run in this notebook’s Python PHOEBE runtime.';

export const canOpenAdvancedWorkspace=config=>!config;
export const isNativeProjectJson=value=>Array.isArray(value);

export function applyColabRuntimeUI(doc,config){
  if(!config)return false;
  doc.getElementById('engine-runtime').innerHTML='Calculated by <a href="https://phoebe-project.org/" target="_blank" rel="noreferrer">PHOEBE 2.5.4</a> in this Colab Python runtime';
  doc.querySelector('footer span:last-child').textContent='Uploaded observations stay in this Colab session.';
  const nativeButton=doc.getElementById('native-button');
  nativeButton.disabled=true;nativeButton.title='The separate PHOEBE file workspace is available in the standalone browser build.';
  doc.getElementById('data-file').accept='.csv,.tsv,.txt,.dat,.json';
  doc.querySelector('label[for="data-file"] span:last-of-type').textContent='CSV, TSV, TXT, or PHOEBE Lab session JSON';
  const runtimeGuide=[...doc.querySelectorAll('#guide-dialog p')].find(p=>p.textContent.includes('What is actually running?'));
  if(runtimeGuide)runtimeGuide.innerHTML='<strong>What is actually running?</strong> Instant trained previews and orbit playback run in this browser. Exact light curves, bounded fits, residual statistics, CSV results, and native surface meshes run with PHOEBE 2.5.4 in this Colab notebook’s native Python process. Changing geometry or donor cancels or supersedes the old request and invalidates its exact statistics/export. The standalone page instead uses the reviewed WebAssembly worker.';
  return true;
}
