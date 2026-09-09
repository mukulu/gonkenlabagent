"""Explicit local maintenance/diagnostic commands; no privileged mutation."""
import json
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
    doctor=subparsers.add_parser('doctor',help='report software/voice readiness without mutation')
    config_arguments(doctor)
    doctor.add_argument('--index',type=Path)
    doctor.add_argument('--probe-ollama',action='store_true',help='explicit local API probe')


def effective(args):
    kw={'cli_overrides':parse_cli_overrides(args.set)}
    if args.no_site: kw['site_path']=None
    elif args.site is not None: kw['site_path']=args.site
    return load_config(**kw).config


def doctor(config,index_path=None,probe_ollama=False):
    rows=[ComponentHealth('config',Readiness.READY,'VALID'), ComponentHealth('privacy',Readiness.READY,'OFFLINE_CONTENT_FREE')]
    for name in ('whisper','piper','input_audio','output_audio','gpio'):
        rows.append(ComponentHealth(name,Readiness.DEGRADED,'PROVISIONING_OR_PHYSICAL_VALIDATION_PENDING'))
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
    data['scope']='voice-appliance-readiness; host implementation is not target acceptance'
    return data


def execute(args):
    config=effective(args)
    corpus=config.paths.corpus_dir
    if args.command=='support':
        from .support import create_bundle
        kw={'cli_overrides':parse_cli_overrides(args.set)}
        if args.no_site:kw['site_path']=None
        elif args.site is not None:kw['site_path']=args.site
        effective_config=load_config(**kw)
        ids=[]
        if args.index:ids=[c['id'] for c in load(args.index,corpus)['chunks']]
        result=create_bundle(args.output,effective_config,doctor(config,args.index),args.telemetry,ids)
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
        data=doctor(config,args.index,args.probe_ollama)
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
