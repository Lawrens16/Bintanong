import asyncio
import importlib
import json


def corpus_module():
    return importlib.import_module('backend.bintanong_agent.corpus')


def search_module():
    return importlib.import_module('backend.bintanong_agent.search')


def make_chunk(chunk_id, body):
    return {'chunk_id': chunk_id, 'chunk_type': 'policy', 'version_id': 'v1', 'source_label': 'Synthetic.pdf',
            'type_fields': {'reading_id': chunk_id.upper(), 'source_limits': [], 'required_neighbor_chunk_ids': []},
            'spans': [{'page': 1}],
            'text': json.dumps({'fields': [{'name': 'body', 'source_blank': False, 'value': body}]})}


def make_corpus(count=0):
    bodies = {'a': 'Library books are due in seven days.', 'b': 'Pay the enrolment fee at the cashier.',
              'c': 'Dormitory curfew starts at ten.'}
    bodies.update({f'x{i:02d}': f'Cashier window note {i}.' for i in range(count)})
    snapshot = {'versions': {}, 'chunks': [make_chunk(k, v) for k, v in bodies.items()]}
    return corpus_module().Corpus.from_snapshot(snapshot)


def test_keyword_search_ranks_matching_passage_first():
    search = search_module().KeywordSearch(make_corpus())
    found = asyncio.run(search.search('where to pay the fee at cashier'))
    assert found[0].chunk_id == 'b'


def test_keyword_search_returns_empty_for_no_overlap():
    assert asyncio.run(search_module().KeywordSearch(make_corpus()).search('zebra')) == ()


def test_top_k_is_clamped_to_eight():
    search = search_module().KeywordSearch(make_corpus(count=12))
    assert len(asyncio.run(search.search('cashier', top_k=50))) == 8
    assert len(asyncio.run(search.search('cashier', top_k=0))) == 1


class FakeEncoder:
    config = type('Config', (), dict(model_id='m', model_revision='r', dimension=2, normalization='l2',
        prompt_fingerprint='p', preprocessing_fingerprint='q', tokenizer_fingerprint='t', max_context_length=8))()

    def __init__(self):
        self.queries = []

    def encode(self, query):
        self.queries.append(query)
        return (1.0, 0.0)


class FakeClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params, role=None):
        self.calls.append((name, params, role))
        return {'status': 'ok', 'release_id': 'rel-1', 'items': [
            {'chunk': {'chunk_id': 'unknown-id'}}, {'chunk': {'chunk_id': 'c'}}, {'chunk': {'chunk_id': 'a'}}]}

    def __getattr__(self, name):
        raise AssertionError('only rpc reads are allowed, not ' + name)


def test_vector_search_passes_stored_embedding_configuration():
    encoder, client = FakeEncoder(), FakeClient()
    search = search_module().VectorSearch(make_corpus(), encoder, client, 'rel-1')
    found = asyncio.run(search.search('curfew', top_k=2))
    assert [p.chunk_id for p in found] == ['c', 'a']
    (name, params, role), = client.calls
    assert (name, role, encoder.queries) == ('retrieve_context', 'runtime', ['curfew'])
    assert params['p_release_id'] == 'rel-1' and params['p_top_k'] == 2
    assert params['p_config']['model_revision'] == 'r' and params['p_config']['dimension'] == 2
    assert params['query_embedding'] == [1.0, 0.0]
