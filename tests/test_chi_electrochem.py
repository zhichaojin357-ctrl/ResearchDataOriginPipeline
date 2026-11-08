from pathlib import Path
import math
import pytest
from src.core.chi_electrochem import parse_chi_name, read_chi_impedance, calculate_chi_mott
from src.core.chi_electrochem import historical_cs_evidence, run_chi_electrochem
import zipfile


@pytest.mark.parametrize('name,material,repeat,kind,condition', [
    ('2-7.5% eis 800s.txt', '7.5%', 2, 'EIS', 800),
    ('7.5% mt 3000hz.csv.bin', '7.5%', 1, 'MT', 3000),
    ('3bob eis 800s.bin', 'BOB', 3, 'EIS', 800),
    ('bob eis 800s-3.csv', 'BOB', 3, 'EIS', 800),
    ('wytbob eis 160s.txt', 'wytbob', 1, 'EIS', 160),
    ('2-bob mt 4000hz.txt', 'BOB', 2, 'MT', 4000),
])
def test_names(name, material, repeat, kind, condition):
    r = parse_chi_name(Path(name))
    assert (r['material'], r['repeat'], r['kind'], r['condition']) == (material, repeat, kind, condition)


def table_file(tmp_path, rows, unit='V'):
    p = tmp_path / 'sample.txt'
    p.write_text('Oct. 30, 2026\nImpedance - Potential\nInstrument Model:  CHI660E\nFrequency (Hz) = 3e+3\n\n'
                 + f'Potential/{unit}, Z\'/ohm, Z"/ohm, Z/ohm, Phase/deg\n\n' + rows, encoding='utf-8')
    return p


def test_raw_impedance_cs_and_frequency(tmp_path):
    t = read_chi_impedance(table_file(tmp_path, '-0.2, 10, -2, 10.2, -11\n0, 11, -3, 11.4, -15\n'))
    r = calculate_chi_mott(t, 3000)
    assert r['plot_eligible']
    assert r['points'][0]['Cs_F'] == pytest.approx(1/(2*math.pi*3000*2))
    assert r['points'][0]['one_over_Cs_squared_F-2'] == pytest.approx((2*math.pi*3000*2)**2)
    assert all(c['relative_error'] < 1e-14 for c in r['checks'])
    with pytest.raises(ValueError, match='frequency'):
        calculate_chi_mott(t, 1000)


def test_invalid_impedance_preserved_and_mv_conversion(tmp_path):
    t = read_chi_impedance(table_file(tmp_path, '-200, 10, 0, 10, 0\n0, 11, 3, 11.4, 15\n', 'mV'))
    r = calculate_chi_mott(t, 3000)
    assert not r['plot_eligible']
    assert r['points'][0]['potential_V'] == -.2
    assert [p['Cs_F'] for p in r['points']] == [None, None]
    assert len(r['points']) == 2


def test_scan_reversal_not_sorted_or_joined(tmp_path):
    t = read_chi_impedance(table_file(tmp_path, '0, 10, -2, 10.2, -11\n.2, 11, -3, 11.4, -15\n0, 10, -2, 10.2, -11\n'))
    r = calculate_chi_mott(t, 3000)
    assert not r['plot_eligible']
    assert [p['potential_V'] for p in r['points']] == [0, .2, 0]


def test_unverified_column_units_rejected(tmp_path):
    p = table_file(tmp_path, '0, 10, -2, 10.2, -11\n')
    p.write_text(p.read_text().replace("Z'/ohm", "Z'/kohm"))
    with pytest.raises(ValueError, match='units'):
        read_chi_impedance(p)


def test_historical_cs_evidence_reads_formulas_without_modifying_source(tmp_path):
    path = tmp_path / 'history.xlsx'
    xml = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="17"><c r="H17"><f>-1/(2*3.1415926*3000*C17)</f></c><c r="I17"><f>1/(H17*H17)</f></c></row></sheetData></worksheet>'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('xl/worksheets/sheet1.xml', xml)
    original = path.read_bytes()
    evidence = historical_cs_evidence(path)
    assert evidence['model'] == 'Cs'
    assert len(evidence['formulas']) == 2
    assert path.read_bytes() == original


def test_batch_deduplicates_formats_and_preserves_binary(tmp_path, monkeypatch):
    source = tmp_path / 'input'
    source.mkdir()
    p = table_file(source, '-.2,10,-2,10.2,-11\n0,11,-3,11.4,-15\n')
    p = p.rename(source / 'bvo mt 3000hz.txt')
    (source / 'bvo mt 3000hz.csv').write_bytes(p.read_bytes())
    (source / 'bvo mt 3000hz.bin').write_bytes(b'\x00original binary')
    before = {f.name: f.read_bytes() for f in source.iterdir()}
    project = tmp_path / 'project'
    project.mkdir()
    registry = Path(__file__).resolve().parents[1] / 'config/processor_registry.yaml'
    monkeypatch.setattr('src.core.chi_electrochem._workbook_export', lambda *args: None)
    monkeypatch.setattr('src.core.chi_electrochem._snapshot_scripts', lambda *args: None)
    monkeypatch.setattr('src.core.chi_electrochem.registry_path', lambda *args: registry)
    m = run_chi_electrochem(project, input_dir=source,
                           output_root=tmp_path / 'out', package_name='batch', with_origin=False,
                           workbook_node=Path('node'), node_modules=Path('unused'))
    assert m['source_file_count'] == 3
    assert m['measurement_counts_by_type'] == {'MT': 1}
    assert m['records'][0]['txt_csv_agree'] is True
    assert m['valid_MT_point_count'] == 2
    assert {f.name: f.read_bytes() for f in source.iterdir()} == before
    with pytest.raises(FileExistsError):
        run_chi_electrochem(project, input_dir=source,
                           output_root=tmp_path / 'out', package_name='batch', with_origin=False,
                           workbook_node=Path('node'), node_modules=Path('unused'))


def test_eis_origin_bridge_uses_existing_reader_and_explicit_kohm_units(tmp_path):
    from src.origin.chi_mott import prepare_chi_origin_jobs
    project = tmp_path / 'project'
    project.mkdir()
    source = tmp_path / 'input'
    source.mkdir()
    name = 'bvo eis 800s.txt'
    (source / name).write_text('A.C. Impedance\nInstrument Model: CHI660E\n\nFreq/Hz, Z\'/ohm, Z"/ohm, Z/ohm, Phase/deg\n1000,10,-2,10.198,-11.3\n100,20,-4,20.396,-11.3\n10,30,-6,30.594,-11.3\n',encoding='utf8')
    stage = tmp_path / 'stage'
    stage.mkdir()
    record = {'id':'M001','kind':'EIS','material':'BVO','repeat':1,'condition':800,
              'source_files':[name],'input_directory':str(source),'row_count':3,'warnings':[]}
    item = prepare_chi_origin_jobs(project,tmp_path/'results',stage,[],[record])[0]
    assert item['rows'][0] == [.01,.002]
    assert item['raw_rows'][0][:2] == [10,2]
    assert len(item['rows']) == 3
    assert item['job'].column_count == 2
    assert item['job'].x_title == "Z' (kΩ)"
    assert item['reader_metadata']['ohm_to_plot_multiplier'] == .001
