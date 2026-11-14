import importlib
import json


def corpus_module():
    return importlib.import_module('backend.bintanong_agent.corpus')


def make_chunk(chunk_id, reading_id, fields, *, group=None, limits=(), neighbours=(), page=3,
               source='Synthetic Handbook.pdf'):
    type_fields = {'reading_id': reading_id, 'source_limits': [{'message': m} for m in limits],
                   'required_neighbor_chunk_ids': list(neighbours)}
    if group:
        type_fields['service_group'] = {'logical_step_id': group, 'part_order': 0, 'part_count': 1}
    return {'chunk_id': chunk_id, 'chunk_type': 'policy', 'version_id': 'v1', 'source_label': source,
            'type_fields': type_fields, 'spans': [{'page': page, 'printed_page_label': str(page - 1)}],
            'text': json.dumps({'fields': [{'name': n, 'source_blank': v == '', 'value': v}
                                           for n, v in fields.items()]})}


def sample_snapshot():
    return {'versions': {'v1': {}}, 'chunks': [
        make_chunk('zz-last', 'F02', {'body': 'Pay the fee at the cashier.'}, group='enrol-step',
                   limits=('Unavailable information: fee amount.',)),
        make_chunk('aa-first', 'F01', {'service_title': 'Enrolment of freshmen', 'body': 'Bring your form.'},
                   group='enrol-step', neighbours=['zz-last', 'not-in-corpus']),
        make_chunk('mm-mid', 'rules-II.14B', {'body': 'Library books are due in seven days.'}),
    ]}


def test_short_ids_are_stable_and_sorted():
    corpus = corpus_module().Corpus.from_snapshot(sample_snapshot())
    assert [(p.short_id, p.chunk_id) for p in corpus.passages] == [
        ('C001', 'aa-first'), ('C002', 'mm-mid'), ('C003', 'zz-last')]
    assert corpus.get('C002').chunk_id == 'mm-mid'
    try:
        corpus.get('C999')
    except KeyError:
        pass
    else:
        raise AssertionError('unknown short id must raise KeyError')


def test_passage_text_keeps_field_names_and_source_limits():
    corpus = corpus_module().Corpus.from_snapshot(sample_snapshot())
    first, last = corpus.get('C001'), corpus.get('C003')
    assert 'service_title: Enrolment of freshmen' in first.text
    assert 'body: Bring your form.' in first.text
    assert last.limits == ('Unavailable information: fee amount.',)
    assert 'Unavailable information: fee amount.' in last.text
    assert (first.source, first.page, first.title) == ('Synthetic Handbook.pdf', 3, 'Enrolment of freshmen')


def test_with_neighbours_adds_required_neighbours_once():
    corpus = corpus_module().Corpus.from_snapshot(sample_snapshot())
    assert corpus.get('C001').neighbour_ids == ('C003',)
    got = corpus.with_neighbours(['C001', 'C003', 'C001'])
    assert [p.short_id for p in got] == ['C001', 'C003']


def test_directory_lists_every_topic():
    corpus = corpus_module().Corpus.from_snapshot(sample_snapshot())
    assert [(t.topic_id, t.passage_ids) for t in corpus.topics] == [
        ('enrol-step', ('C001', 'C003')), ('rules-II.14B', ('C002',))]
    listing = corpus.directory()
    assert 'enrol-step' in listing and 'Enrolment of freshmen' in listing
    assert 'rules-II.14B' in listing and 'C002' in listing


def test_topic_falls_back_to_reading_id_without_trailing_number():
    snapshot = {'versions': {}, 'chunks': [make_chunk('c1', 'F01', {'body': 'x'}),
                                           make_chunk('c2', '12', {'body': 'y'})]}
    assert [t.topic_id for t in corpus_module().Corpus.from_snapshot(snapshot).topics] == ['12', 'F']


def test_empty_source_limit_strings_are_dropped():
    chunk = make_chunk('c1', 'F01', {'body': 'x'}, limits=('', 'Real limit.'))
    passage = corpus_module().Corpus.from_snapshot({'versions': {}, 'chunks': [chunk]}).get('C001')
    assert passage.limits == ('Real limit.',)
    assert passage.text.splitlines()[-2:] == ['Source limits:', '- Real limit.']
