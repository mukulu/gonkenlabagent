"""Reproducible retrieval smoke benchmark; never labels synthetic data as lab evidence."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gonken_agent.retrieval.index import build, retrieve, digest
from gonken_agent.llm.prompts import extractive


def evaluate(index,cases):
    known=unknown=hit=abstained=answered=valid=0
    details=[]
    for case in cases:
        hits=retrieve(index,case['query'])
        answer=extractive(hits)
        is_known=bool(case['expected_paths'])
        found=any(h['path'] in case['expected_paths'] for h in hits)
        if is_known: known+=1; hit+=found
        else: unknown+=1; abstained+=answer.abstain
        if not answer.abstain:
            answered+=1
            valid+=all(i in {h['id'] for h in hits} for i in answer.source_ids)
        details.append({'id':case['id'],'answerable':is_known,'hit_at_3':found if is_known else None,
                        'abstained':answer.abstain,'source_ids':list(answer.source_ids)})
    return {'schema':1,'evidence_tier':'T1 synthetic retrieval smoke only',
            'mode':'extractive; no real model, speech, timing, RAM or thermal benchmark',
            'evaluation_sha256':digest(cases),'index_checksum':index['checksum'],
            'answerable':known,'unanswerable':unknown,'hit_at_3':hit/known if known else None,
            'unsupported_abstention':abstained/unknown if unknown else None,
            'valid_source_id_coverage':valid/answered if answered else None,
            'limitations':['Templated synthetic equipment documents, not actual lab policy.',
                          'Out-of-domain negatives do not establish in-domain abstention.',
                          'Source ID validity is not factual entailment.'], 'cases':details}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,default=Path(__file__).resolve().parents[1]/'tests/fixtures/grounding')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    index=build(args.fixtures/'corpus',json.loads((args.fixtures/'calibration.json').read_text()))
    result=evaluate(index,json.loads((args.fixtures/'evaluation.json').read_text()))
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},sort_keys=True))

if __name__=='__main__': main()
