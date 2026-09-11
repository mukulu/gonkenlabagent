"""Export only newly constructed allow-listed diagnostic data, never raw files."""
import json
import os
import platform
import tempfile
import zipfile
from pathlib import Path
from . import __version__
from .health import COMPONENTS
from .telemetry import validate_event
from .diagnostics import load_snapshot


def create_bundle(output, effective_config, health, telemetry_path=None, allowed_source_ids=(), startup_snapshot=None):
    output=Path(output).absolute()
    if output.exists() or output.is_symlink() or output.parent.resolve()!=output.parent:
        raise ValueError('support output must be a new file in a safe directory')
    # Caller-supplied health detail is not copied. Only schema-validated categories survive.
    rows=[]
    for row in health.get('components',[]):
        if row.get('component') not in COMPONENTS or row.get('status') not in {'READY','FAILED','DEGRADED','MAINTENANCE'}:
            raise ValueError('invalid support health')
        rows.append({'component':row['component'],'status':row['status']})
    events=[]
    if telemetry_path is not None:
        path=Path(telemetry_path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>8*1024*1024:
            raise ValueError('unsafe support telemetry input')
        with path.open('rb') as stream:
            raw=stream.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:raise ValueError('telemetry limit')
        for line in raw.splitlines()[-100:]:
            record=json.loads(line)
            # Drop timestamps rather than treating arbitrary timestamp strings as trusted.
            record.pop('timestamp',None)
            events.append(validate_event(record,allowed_source_ids))
    files={
        'environment.json':{'schema':1,'package_version':__version__,'python':platform.python_version(),
                            'system':platform.system(),'architecture':platform.machine(),
                            'target_acceptance':'not_established_by_support_export'},
        'configuration.json':{'config':effective_config.as_dict(redact=True),'sources':effective_config.source_dict()},
        'health.json':{'components':rows},
        'telemetry.json':{'content_logging':False,'events':events},
    }
    if startup_snapshot is not None:
        files['startup_snapshot.json']=load_snapshot(startup_snapshot)
    fd,temporary=tempfile.mkstemp(prefix='.support-',dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,value in sorted(files.items()):
                entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.external_attr=0o100600<<16
                entry.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(entry,json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')
        with open(temporary,'rb') as stream:os.fsync(stream.fileno())
        # Hard link is atomic and fails if another writer created output meanwhile.
        os.link(temporary,output,follow_symlinks=False)
    finally:Path(temporary).unlink(missing_ok=True)
    return {'status':'CREATED','members':sorted(files),'content_logging':False}
