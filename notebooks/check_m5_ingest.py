"""Local response fixtures prove checkpoint and full-history replay; no live API calls."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import ingest


class Response:
    status_code = 200

    def __init__(self, rows):
        self.content = json.dumps(rows).encode()

    def json(self):
        return json.loads(self.content)


def check():
    base = ROOT/'tmp/m5'
    base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as folder:
        directory = Path(folder)
        state = directory/'state.json'
        urls = []

        def response(url,tokens):
            urls.append(url)
            if url.endswith('/localities'):
                return Response([{'localityNo':10292}])
            if '/liceTreatments/' in url:
                return Response([])
            if '/seatemperature/' in url:
                return Response([{'week':1,'seaTemperature':7,'hasReported':True}])
            return Response([{'week':1,'value':.1}])

        clock = datetime(2022,2,1,tzinfo=timezone.utc)
        with patch.object(ingest,'RAW_DIR',directory/'raw'), patch.object(ingest,'TokenManager'), \
             patch.object(ingest,'make_request',side_effect=response), patch.object(ingest.time,'sleep'):
            first = ingest.ingest(clock,state_path=state,no_dotenv=True)
            assert first['requests']==121
            assert len(urls)==121
            original = state.read_bytes()
            with patch.object(ingest,'make_request',side_effect=RuntimeError('fixture outage')):
                try:
                    ingest.ingest(datetime(2022,2,3,tzinfo=timezone.utc),state_path=state,no_dotenv=True)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('Failure swallowed')
            assert state.read_bytes()==original
            urls.clear()
            ingest.ingest(datetime(2022,2,4,tzinfo=timezone.utc),state_path=state,no_dotenv=True)
            assert len(urls)==121 and all('/2022' in url for url in urls[1:])
            original = state.read_bytes()
            with patch.object(ingest,'make_request',return_value=Response([])):
                try:
                    ingest.ingest(datetime(2022,2,5,tzinfo=timezone.utc),state_path=state,no_dotenv=True)
                except ValueError:
                    pass
                else:
                    raise AssertionError('Empty required source accepted')
            assert state.read_bytes()==original
    result = {'fixture_only':True,'full_history_replayed_after_outage':True,
              'failed_run_does_not_advance_checkpoint':True,'empty_required_source_rejected':True,
              'empty_treatment_year_accepted':True}
    (ROOT/'docs/evidence/m5_ingest_checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    check()
