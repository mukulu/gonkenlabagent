"""Explicit local maintenance/diagnostic commands; no privileged mutation."""
import json
import time
import signal
import sys
import threading
from pathlib import Path
from .config import load_config, parse_cli_overrides
from .health import ComponentHealth, Readiness, summary
from .retrieval.index import build, load, save, sources
from .llm.ollama import OllamaClient
from .runtime import Coordinator, signal_handlers
from .text_pipeline import TextPipeline
from .telemetry import Telemetry
from .dashboard import Snapshot, server
from .diagnostics import default_snapshot_dir, write_startup_snapshot, collect_environment_diagnostics


def config_arguments(parser):
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--site',type=Path)
    group.add_argument('--no-site',action='store_true')
    parser.add_argument('--set',action='append',default=[],metavar='SECTION.FIELD=VALUE')


def add_commands(subparsers):
    index=subparsers.add_parser('index',help='build or verify a calibrated local corpus index')
    index.add_argument('action',choices=['build','verify'])
    config_arguments(index)
    index.add_argument('--index',type=Path,required=True)
    index.add_argument('--calibration',type=Path,help='JSON development cases; required for build')
    ask=subparsers.add_parser('ask',help='run one explicit grounded text diagnostic')
    config_arguments(ask)
    ask.add_argument('question')
    ask.add_argument('--index',type=Path,required=True)
    ask.add_argument('--extractive',action='store_true',help='quote a retrieved excerpt without running Ollama')
    ask.add_argument('--telemetry',type=Path,help='explicit content-free JSONL output')
    dashboard=subparsers.add_parser('dashboard',help='serve read-only loopback diagnostic health')
    config_arguments(dashboard)
    dashboard.add_argument('--index',type=Path,required=True)
    support=subparsers.add_parser('support',help='create an allow-listed private diagnostic ZIP')
    config_arguments(support)
    support.add_argument('--output',type=Path,required=True)
    support.add_argument('--index',type=Path)
    support.add_argument('--telemetry',type=Path)
    support.add_argument('--startup-snapshot',type=Path)
    doctor=subparsers.add_parser('doctor',help='report software/voice readiness without mutation')
    config_arguments(doctor)
    doctor.add_argument('--index',type=Path)
    doctor.add_argument('--probe-ollama',action='store_true',help='explicit local API probe')
    doctor.add_argument('--probe-audio',action='store_true',help='open the configured physical input/output paths')
    doctor.add_argument('--write-startup-snapshot',action='store_true',
                        help='write a content-free platform snapshot for support upload')
    doctor.add_argument('--snapshot-dir',type=Path)
    doctor.add_argument('--diagnostic-mode',choices=['debug','production'],default='debug')
    doctor.add_argument('--retain-startup-snapshots',type=int)
    service=subparsers.add_parser('service',help='run the governed headless service supervisor')
    config_arguments(service)
    service.add_argument('--index',type=Path)
    service.add_argument('--probe-ollama',action='store_true',help='explicit local API probe')
    service.add_argument('--once',action='store_true',help='emit one content-free service status and exit')
    service.add_argument('--snapshot-dir',type=Path)
    service.add_argument('--diagnostic-mode',choices=['debug','production'],default='debug')
    service.add_argument('--retain-startup-snapshots',type=int)


def effective(args):
    kw={'cli_overrides':parse_cli_overrides(args.set)}
    if args.no_site: kw['site_path']=None
    elif args.site is not None: kw['site_path']=args.site
    return load_config(**kw).config


def doctor(config,index_path=None,probe_ollama=False,probe_audio=False):
    rows=[ComponentHealth('config',Readiness.READY,'VALID'), ComponentHealth('privacy',Readiness.READY,'OFFLINE_CONTENT_FREE')]
    whisper_ready=Path(config.paths.whisper_binary).is_file() and Path(config.paths.whisper_model).is_file()
    piper_ready=Path('/usr/local/bin/piper').is_file() and Path(config.paths.piper_voice).is_file()
    rows.append(ComponentHealth('whisper',Readiness.READY if whisper_ready else Readiness.DEGRADED,
                                'LOCAL_STT_PRESENT' if whisper_ready else 'LOCAL_STT_MISSING'))
    rows.append(ComponentHealth('piper',Readiness.READY if piper_ready else Readiness.DEGRADED,
                                'LOCAL_TTS_PRESENT' if piper_ready else 'LOCAL_TTS_MISSING'))
    if probe_audio:
        try:
            from .voice_runtime import AudioBackend
            AudioBackend(config).probe()
        except (ValueError,OSError,RuntimeError):
            rows.extend((ComponentHealth('input_audio',Readiness.DEGRADED,'PHYSICAL_AUDIO_UNAVAILABLE'),
                         ComponentHealth('output_audio',Readiness.DEGRADED,'PHYSICAL_AUDIO_UNAVAILABLE')))
        else:
            rows.extend((ComponentHealth('input_audio',Readiness.READY,'PHYSICAL_INPUT_OPENED'),
                         ComponentHealth('output_audio',Readiness.READY,'PHYSICAL_OUTPUT_OPENED')))
    else:
        rows.extend((ComponentHealth('input_audio',Readiness.DEGRADED,'PHYSICAL_AUDIO_NOT_PROBED'),
                     ComponentHealth('output_audio',Readiness.DEGRADED,'PHYSICAL_AUDIO_NOT_PROBED')))
    rows.append(ComponentHealth('gpio',Readiness.DEGRADED,'GPIO_OPTIONAL_NOT_PROBED'))
    environment_detail = environment_health(config)
    rows.append(ComponentHealth('environment', environment_detail['component_status'], environment_detail['component_code']))
    if index_path:
        try: load(index_path,config.paths.corpus_dir)
        except (ValueError,OSError): rows.append(ComponentHealth('index',Readiness.FAILED,'INDEX_INVALID_OR_STALE'))
        else: rows.append(ComponentHealth('index',Readiness.READY,'VALID'))
    else: rows.append(ComponentHealth('index',Readiness.DEGRADED,'INDEX_NOT_PROBED'))
    if probe_ollama:
        client=OllamaClient(config.llm,timeout=3)
        try: client.model_identity(threading.Event())
        except (ValueError,RuntimeError,OSError): rows.append(ComponentHealth('ollama',Readiness.DEGRADED,'LOCAL_MODEL_UNAVAILABLE'))
        else: rows.append(ComponentHealth('ollama',Readiness.READY,'LOCAL_MODEL_PRESENT'))
        finally: client.close()
    else: rows.append(ComponentHealth('ollama',Readiness.DEGRADED,'NOT_PROBED'))
    data=summary(rows)
    data['scope']='local software and optional physical audio readiness'
    ready_file=Path('/run/gonken-agent/ready.json')
    data['voice_runtime']='ready' if ready_file.is_file() else 'waiting_or_stopped'
    data['environment']=_public_environment_health(environment_detail)
    return data


def environment_health(config) -> dict[str, object]:
    diagnostics = collect_environment_diagnostics(config, mode='production')
    if not diagnostics.get('enabled'):
        status = Readiness.DEGRADED
        code = 'ENVIRONMENT_DISABLED'
    else:
        ipc = diagnostics.get('ipc') if isinstance(diagnostics.get('ipc'), dict) else {}
        overall = ipc.get('overall')
        if ipc.get('status') != 'READY':
            status = Readiness.DEGRADED
            code = 'ENVIRONMENT_IPC_UNAVAILABLE'
        elif overall == 'READY':
            status = Readiness.READY
            code = 'ENVIRONMENT_READY'
        elif overall == 'FAILED':
            status = Readiness.FAILED
            code = 'ENVIRONMENT_FAILED'
        else:
            status = Readiness.DEGRADED
            code = 'ENVIRONMENT_DEGRADED'
    return {'component_status': status, 'component_code': code, 'diagnostics': diagnostics}


def _public_environment_health(detail: dict[str, object]) -> dict[str, object]:
    diagnostics = detail.get('diagnostics') if isinstance(detail.get('diagnostics'), dict) else {}
    ipc = diagnostics.get('ipc') if isinstance(diagnostics.get('ipc'), dict) else {}
    static = diagnostics.get('static') if isinstance(diagnostics.get('static'), dict) else {}
    capabilities = diagnostics.get('capabilities') if isinstance(diagnostics.get('capabilities'), dict) else {}
    return {
        'status': detail['component_status'].value if isinstance(detail.get('component_status'), Readiness) else str(detail.get('component_status')),
        'code': str(detail.get('component_code')),
        'enabled': bool(diagnostics.get('enabled', False)),
        'ipc': {
            'status': ipc.get('status', 'UNKNOWN'),
            'code': ipc.get('code', 'UNKNOWN'),
            'overall': ipc.get('overall', 'UNKNOWN'),
            'physical_evidence': bool(ipc.get('physical_evidence', False)),
        },
        'sensor_backend': static.get('sensor_backend', 'unknown'),
        'i2c_bus': static.get('i2c_bus', 'unknown'),
        'i2c_address_hex': static.get('i2c_address_hex', 'unknown'),
        'relay_backend': static.get('relay_backend', 'unknown'),
        'relay_bcm': static.get('relay_bcm', 'unknown'),
        'capabilities': capabilities,
        'target_acceptance': diagnostics.get('target_acceptance', 'not_established_by_diagnostics'),
        'physical_evidence': bool(diagnostics.get('physical_evidence', False)),
    }


def service_loop(args):
    config=effective(args)
    try:
        snapshot=write_startup_snapshot(config,directory=args.snapshot_dir,
                                        mode=args.diagnostic_mode,
                                        retain=args.retain_startup_snapshots)
        snapshot_state={'status':snapshot['status'],'mode':snapshot['mode'],'retention':snapshot['retention']}
    except (ValueError,OSError):
        snapshot_state={'status':'FAILED','mode':args.diagnostic_mode}
    if args.once:
        data=doctor(config,args.index,args.probe_ollama,False)
        data.update({'service':'gonken-agent','mode':'voice-appliance','startup_snapshot':snapshot_state,'ready_for_systemd':True})
        print(json.dumps(data,sort_keys=True),flush=True)
        return 0
    print(json.dumps({'service':'gonken-agent','status':'STARTING','mode':'voice-appliance',
                      'startup_snapshot':snapshot_state},sort_keys=True),flush=True)
    from .voice_runtime import run_appliance
    return run_appliance(config, foreground=False)



def execute(args):
    config=effective(args)
    corpus=config.paths.corpus_dir
    if args.command=='service':
        return service_loop(args)
    if args.command=='support':
        from .support import create_bundle
        kw={'cli_overrides':parse_cli_overrides(args.set)}
        if args.no_site:kw['site_path']=None
        elif args.site is not None:kw['site_path']=args.site
        effective_config=load_config(**kw)
        ids=[]
        if args.index:ids=[c['id'] for c in load(args.index,corpus)['chunks']]
        result=create_bundle(args.output,effective_config,doctor(config,args.index),args.telemetry,ids,args.startup_snapshot)
        print(json.dumps(result,sort_keys=True))
        return 0
    if args.command=='index':
        if args.action=='build':
            if not args.calibration or args.calibration.stat().st_size>1024*1024:
                raise ValueError('bounded calibration JSON is required')
            cases=json.loads(args.calibration.read_text())
            index=build(corpus,cases)
            save(index,args.index)
        else: index=load(args.index,corpus)
        print(json.dumps({'status':'VALID','sources':len(index['sources']),'chunks':len(index['chunks']),
                          'checksum':index['checksum'],'calibration':index['calibration']},sort_keys=True))
        return 0
    if args.command=='doctor':
        data=doctor(config,args.index,args.probe_ollama,getattr(args,'probe_audio',False))
        if args.write_startup_snapshot:
            snapshot=write_startup_snapshot(config,directory=args.snapshot_dir,
                                            mode=args.diagnostic_mode,
                                            retain=args.retain_startup_snapshots)
            data['startup_snapshot']={'status':snapshot['status'],
                                      'mode':snapshot['mode'],
                                      'retention':snapshot['retention'],
                                      'default_dir': str(default_snapshot_dir(config))}
        print(json.dumps(data,sort_keys=True))
        return data['exit_code']
    if args.command=='ask':
        if not config.retrieval.enabled:
            raise ValueError('grounded text diagnostics require retrieval enabled')
        index=load(args.index,corpus)
        ids=[c['id'] for c in index['chunks']]
        telemetry=Telemetry(args.telemetry,ids) if args.telemetry else None
        client=None if args.extractive else OllamaClient(config.llm)
        pipeline=TextPipeline(args.index,corpus,client=client,top_k=config.retrieval.top_k,telemetry=telemetry)
        coordinator=Coordinator(pipeline)
        try:
            with signal_handlers(coordinator):
                coordinator.activate(args.question)
                answer=coordinator.step()
                if answer is None:
                    print(json.dumps({'status':'DEGRADED','code':'TEXT_PIPELINE_FAILED_OR_CANCELLED'}))
                    return 2
                print(json.dumps(answer.as_dict(),sort_keys=True))
                return 0
        finally: coordinator.close()
    if args.command=='dashboard':
        if not config.dashboard.enabled: raise ValueError('dashboard disabled by configuration')
        load(args.index,corpus)
        snapshot=Snapshot(transient=config.privacy.dashboard_transient_content)
        snapshot.update({'state':'DEGRADED','status':'DEGRADED'})
        snapshot.update_environment(_public_environment_health(environment_health(config)))
        httpd=server(snapshot,config.dashboard.bind,config.dashboard.port)
        httpd.timeout=.2
        stop=threading.Event()
        old={}
        try:
            for sig in (signal.SIGINT,signal.SIGTERM): old[sig]=signal.signal(sig,lambda *_:stop.set())
            print(json.dumps({'dashboard':'listening','bind':config.dashboard.bind,'port':httpd.server_port,
                              'scope':'standalone diagnostic; no voice runtime connected'}),flush=True)
            while not stop.is_set(): httpd.handle_request()
        finally:
            httpd.server_close(); snapshot.clear()
            for sig,handler in old.items(): signal.signal(sig,handler)
        return 0
    return 3


def text_session(args):
    """One process owns stdin, the coordinator and its optional dashboard."""
    import select
    if not args.index:
        raise ValueError('--text-only requires --index')
    config=effective(args)
    if not config.retrieval.enabled:
        raise ValueError('text diagnostics require retrieval enabled')
    index=load(args.index,config.paths.corpus_dir)
    ids=[chunk['id'] for chunk in index['chunks']]
    snapshot=Snapshot(transient=config.privacy.dashboard_transient_content,allowed_source_ids=ids)
    snapshot.update_environment(_public_environment_health(environment_health(config)))
    telemetry=Telemetry(args.telemetry,ids) if args.telemetry else None
    client=None if args.extractive else OllamaClient(config.llm)
    pipeline=TextPipeline(args.index,config.paths.corpus_dir,client=client,
                          top_k=config.retrieval.top_k,telemetry=telemetry,snapshot=snapshot)
    coordinator=Coordinator(pipeline,lambda state,code:snapshot.transition(
        state,'READY' if state=='IDLE' else 'DEGRADED'))
    httpd=worker=None
    try:
        if args.with_dashboard:
            if not config.dashboard.enabled:raise ValueError('dashboard disabled')
            httpd=server(snapshot,config.dashboard.bind,config.dashboard.port)
            worker=threading.Thread(target=lambda:httpd.serve_forever(poll_interval=.1),daemon=True)
            worker.start()
        print(json.dumps({'mode':'text-diagnostic','voice_ready':False,
                          'dashboard_port':httpd.server_port if httpd else None}),flush=True)
        with signal_handlers(coordinator):
            # Read bytes directly: TextIOWrapper read-ahead can hide queued lines
            # from select() when several input lines arrive in one write.
            pending=b''
            while not coordinator.cancel.is_set():
                if b'\n' not in pending:
                    ready,_,_=select.select([sys.stdin],[],[],.1)
                    if not ready:continue
                    data=__import__('os').read(sys.stdin.fileno(),4096)
                    if not data:
                        if not pending:break
                        pending+=b'\n'
                    else:pending+=data
                if len(pending)>16384:raise ValueError('stdin line bound exceeded')
                if b'\n' not in pending:continue
                raw,pending=pending.split(b'\n',1)
                question=raw.decode('utf-8').strip()
                if not question:continue
                coordinator.refresh()
                if coordinator.activate(question):
                    answer=coordinator.step()
                    print(json.dumps(answer.as_dict() if answer else {'status':'DEGRADED','code':'TEXT_PIPELINE_FAILED_OR_CANCELLED'}),flush=True)
            return 0
    finally:
        coordinator.close()
        if httpd:
            httpd.shutdown();httpd.server_close()
        if worker:worker.join(timeout=2)
