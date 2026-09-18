"""
Скоринг подозрительных анкет опроса Uzum ToM.

Что делает:
  1. Берёт лист 'data' (полные ответы) и лист 'dashboard' (ручная разметка
     брака аналитиком, колонка 'brak') из исходного Excel-файла выгрузки Kobo.
  2. Считает признаки качества интервью: длительность, повтор координат GPS
     у одного интервьюера, straight-lining по шкале согласия, отсутствие
     доп. упоминаний в open-end вопросах, дубликаты телефона и т.п.
  3. Обучает RandomForest предсказывать 'brak' по этим признакам
     (5-fold stratified CV, т.к. класс сильно несбалансирован: ~3% брака).
  4. Считает риск-скор для каждой анкеты и выгружает ранжированный отчёт
     в Excel: общий рейтинг риска, новые кандидаты на проверку (пока
     принятые, но с высоким риском) и сводку по интервьюерам.

Использование:
    python fraud_score_ankety.py /path/to/survey_export.xlsx /path/to/output.xlsx

Требования: pandas, numpy, scikit-learn, openpyxl.
"""
import re
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

warnings.filterwarnings("ignore")

LAT = '_Интервьюер, пожалуйста, зарегистрируйте Ваше местоположение._latitude'
LON = '_Интервьюер, пожалуйста, зарегистрируйте Ваше местоположение._longitude'
PREC = '_Интервьюер, пожалуйста, зарегистрируйте Ваше местоположение._precision'
INTER = 'Код интервьюера'
CITY = 'Город'
GENDER = 'Пол респондента'
AGE = 'Сколько вам полных лет?'
NAME = 'Скажите пожалуйста как вас зовут?'
PHONE = 'Номер телефона респондента'
KNOWN = 'q11_known_count'
FINAL_Q = '15. Вы уже оформляли карту Uzum?'

FEATURE_COLS = [
    'duration_sec', 'completed', 'hour', 'weekday', 'precision_num', 'gps_repeat_count',
    'age_num', 'age_missing', 'gender_missing',
    'name_missing', 'phone_missing', 'phone_is_dummy', 'phone_dup_flag',
    'known_count', 'known_extreme',
    'agree_straightline_ratio', 'agree_answered_n', 'addl_mentions_n',
]


def build_features(path):
    xls = pd.ExcelFile(path)
    data = xls.parse('data')
    dash = xls.parse('dashboard')

    lab = dash[['_id', 'brak', 'отбор']].dropna(subset=['_id'])
    df = data.merge(lab, on='_id', how='left')
    df = df[df['brak'].notna()].copy()
    df['brak'] = df['brak'].astype(int)

    df['start_dt'] = pd.to_datetime(df['start'], errors='coerce', utc=True)
    df['end_dt'] = pd.to_datetime(df['end'], errors='coerce', utc=True)
    df['duration_sec'] = (df['end_dt'] - df['start_dt']).dt.total_seconds()
    df['hour'] = df['start_dt'].dt.tz_convert('Asia/Tashkent').dt.hour
    df['weekday'] = df['start_dt'].dt.tz_convert('Asia/Tashkent').dt.weekday

    df['precision_num'] = pd.to_numeric(df[PREC], errors='coerce')

    # повтор координат у одного интервьюера -> "не двигался между точками"
    df['lat_r'] = df[LAT].round(4)
    df['lon_r'] = df[LON].round(4)
    df['gps_repeat_count'] = df.groupby([INTER, 'lat_r', 'lon_r'])['_id'].transform('count').fillna(1)

    df['age_num'] = pd.to_numeric(df[AGE], errors='coerce')
    df['gender_missing'] = df[GENDER].isna().astype(int)
    df['age_missing'] = df[AGE].isna().astype(int)

    df['name_missing'] = df[NAME].isna().astype(int)
    phone_num = pd.to_numeric(df[PHONE], errors='coerce')
    df['phone_missing'] = phone_num.isna().astype(int)
    dummy_mode = phone_num.mode(dropna=True)
    dummy_value = dummy_mode.iloc[0] if len(dummy_mode) else np.nan
    df['phone_is_dummy'] = (phone_num == dummy_value).astype(int)
    phone_counts = phone_num.value_counts()
    df['phone_dup_count'] = phone_num.map(phone_counts).fillna(0)
    df['phone_dup_flag'] = ((df['phone_dup_count'] > 1) & (phone_num != dummy_value)).astype(int)

    df['known_count'] = pd.to_numeric(df[KNOWN], errors='coerce')
    df['known_extreme'] = ((df['known_count'] <= 1) | (df['known_count'] >= 19)).astype(int)

    # straight-lining по шкале согласия (до 4 продуктов x 3 утверждения = 12 ответов)
    agree_cols = [c for c in data.columns if (
        'подходит для ежедневного' in c or 'выгодные условия' in c or 'могу обратиться' in c
    )]

    def straightline_score(row):
        nums = []
        for c in agree_cols:
            v = row[c]
            if pd.isna(v):
                continue
            m = re.match(r'\s*(\d)', str(v))
            if m:
                nums.append(int(m.group(1)))
        if len(nums) < 3:
            return np.nan
        return nums.count(max(set(nums), key=nums.count)) / len(nums)

    df['agree_straightline_ratio'] = df.apply(straightline_score, axis=1)
    df['agree_answered_n'] = df[agree_cols].notna().sum(axis=1)

    addl_prefixes = ('2.', '6.', '7.', '8.', '9.', '10.')
    addl_cols = [c for c in data.columns if c.startswith(addl_prefixes) and 'А еще' in c]
    df['addl_mentions_n'] = df[addl_cols].notna().sum(axis=1)

    df['completed'] = df[FINAL_Q].notna().astype(int)

    out_cols = ['_id', 'Введите ID анкеты', CITY, INTER, 'today', 'brak', 'отбор'] + FEATURE_COLS
    return df[out_cols].copy()


def train_and_score(work):
    X = work[FEATURE_COLS].copy()
    for c in X.columns:
        X[c] = X[c].fillna(X[c].median())
    y = work['brak'].astype(int)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    clf = RandomForestClassifier(
        n_estimators=400, max_depth=5, min_samples_leaf=3,
        class_weight='balanced_subsample', random_state=42,
    )

    oof_proba = cross_val_predict(clf, X, y, cv=skf, method='predict_proba')[:, 1]
    print("Cross-validated ROC-AUC:", round(roc_auc_score(y, oof_proba), 3))
    print("Cross-validated PR-AUC:", round(average_precision_score(y, oof_proba), 3))
    for k in (34, 50, 70, 100):
        top_idx = np.argsort(-oof_proba)[:k]
        caught = y.values[top_idx].sum()
        print(f"Top {k} riskiest -> catch {caught}/{y.sum()} known brak ({caught / y.sum():.0%})")

    clf.fit(X, y)
    importances = pd.Series(clf.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
    print("\nFeature importances:\n", importances)

    work = work.copy()
    work['risk_score'] = clf.predict_proba(X)[:, 1]
    work['risk_score_oof'] = oof_proba
    return work


def reasons(r):
    tags = []
    if r['completed'] == 1 and r['duration_sec'] < 200:
        tags.append(f"аномально короткая полная анкета ({r['duration_sec']:.0f} сек при плане 7-8 мин)")
    if r['completed'] == 0 and r['duration_sec'] < 30:
        tags.append(f"скрининг закрыт слишком быстро ({r['duration_sec']:.0f} сек) — вопросы вряд ли зачитывались")
    if r['gps_repeat_count'] >= 4:
        tags.append(f"те же координаты повторяются {int(r['gps_repeat_count'])} раз у этого интервьюера")
    if r['phone_dup_flag'] == 1:
        tags.append("телефон респондента повторяется в другой анкете")
    if r['agree_straightline_ratio'] >= 0.9 and r['agree_answered_n'] >= 6:
        tags.append("одинаковые ответы по всей шкале согласия (straight-lining)")
    if r['addl_mentions_n'] == 0 and r['completed'] == 1:
        tags.append("ни одного доп. упоминания в открытых вопросах (2/6/7/8/9/10)")
    if r['known_extreme'] == 1 and r['completed'] == 1:
        tags.append("экстремальная осведомлённость (знает почти все или почти ничего из банков)")
    if r['name_missing'] == 1 and r['phone_missing'] == 1 and r['completed'] == 1:
        tags.append("не указаны имя и телефон респондента, хотя анкета завершена")
    if r['hour'] < 8 or r['hour'] >= 22:
        tags.append(f"необычное время интервью ({int(r['hour'])}:00)")
    if not tags:
        tags.append("совокупность второстепенных признаков (см. числовые столбцы)")
    return "; ".join(tags)


def export_report(scored, out_path):
    scored = scored.copy()
    scored['причины'] = scored.apply(reasons, axis=1)
    scored['статус_ОТК'] = scored['brak'].map({1: 'уже в браке', 0: 'принята'})
    scored['риск_%'] = (scored['risk_score_oof'] * 100).round(1)

    cols = ['Введите ID анкеты', CITY, INTER, 'today', 'статус_ОТК',
            'риск_%', 'причины', 'duration_sec', 'completed', 'agree_straightline_ratio',
            'gps_repeat_count', 'phone_dup_flag', 'known_count', 'addl_mentions_n']
    ranking = scored.sort_values('risk_score_oof', ascending=False)[cols]

    new_candidates = ranking[(ranking['статус_ОТК'] == 'принята') & (ranking['риск_%'] >= 50)]

    interviewer_summary = scored.groupby(INTER).agg(
        анкет_всего=('brak', 'size'),
        в_браке_уже=('brak', 'sum'),
        средний_риск=('risk_score_oof', 'mean'),
        анкет_риск_50плюс=('risk_score_oof', lambda s: (s >= 0.5).sum()),
    ).reset_index()
    interviewer_summary['средний_риск_%'] = (interviewer_summary['средний_риск'] * 100).round(1)
    interviewer_summary = interviewer_summary.drop(columns='средний_риск')
    interviewer_summary = interviewer_summary[interviewer_summary['анкет_всего'] >= 5]
    interviewer_summary = interviewer_summary.sort_values('средний_риск_%', ascending=False)

    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        ranking.to_excel(writer, sheet_name='Рейтинг риска', index=False)
        new_candidates.to_excel(writer, sheet_name='Новые кандидаты на проверку', index=False)
        interviewer_summary.to_excel(writer, sheet_name='По интервьюерам', index=False)

    print("\nSaved:", out_path)
    print("Всего анкет:", len(scored), "| уже в браке:", int((scored['brak'] == 1).sum()),
          "| новых кандидатов на проверку:", len(new_candidates))


if __name__ == '__main__':
    in_path = sys.argv[1] if len(sys.argv) > 1 else 'Uzum_ToM_10.xlsx'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'Podozritelnye_ankety.xlsx'
    features = build_features(in_path)
    scored = train_and_score(features)
    export_report(scored, out_path)
