"""
seed_assessments_pg.py
Seeds SRQ-F (English + Amharic), Hopkins Symptom Checklist, WHOQOL-BREF,
and Big Five Personality Test into the PostgreSQL database using db.py.
"""
import json
import sys
import os

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db as _db

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def upsert_template(conn, name, description, category, tags, lang, created_by=1):
    """Return (template_id, inserted)."""
    row = conn.execute("SELECT id FROM assessment_templates WHERE name = %s", (name,)).fetchone()
    if row:
        print(f"  ↳ '{name}' already exists (id={row['id']}). Skipping.")
        return row['id'], False

    cur = conn.execute(
        """INSERT INTO assessment_templates
           (name, description, form_language, is_public, is_active, created_by, published, category, tags)
           VALUES (%s, %s, %s, 1, 1, %s, 1, %s, %s)
           RETURNING id""",
        (name, description, lang, created_by, category, tags)
    )
    row = cur.fetchone()
    return row['id'], True


def insert_questions(conn, template_id, questions):
    """
    questions: list of dicts with keys:
      key, label, type ('yes_no'|'scale'|'single_choice'|'info'), options (list|None), required
    """
    for i, q in enumerate(questions):
        opts = json.dumps(q.get('options') or [], ensure_ascii=False) if q.get('options') else None
        conn.execute(
            """INSERT INTO assessment_questions
               (template_id, question_key, label_en, question_type, required, options_json, sort_order)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                template_id,
                q.get('key', f'q_{i+1}'),
                q['label'],
                q.get('type', 'yes_no'),
                1 if q.get('required', True) else 0,
                opts,
                q.get('order', i + 1),
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# 1. SRQ-20 / SRQ-F (English)
# ─────────────────────────────────────────────────────────────────────────────

def seed_srq_english(conn):
    name = "Self-Reporting Questionnaire (SRQ-F) - English"
    tid, inserted = upsert_template(
        conn, name,
        "The SRQ is a WHO tool to screen for neurotic disorders. "
        "Answer Yes or No for each item based on the last 30 days.",
        "Mental Health Screening", "SRQ, WHO, screening, mental health",
        "English"
    )
    if not inserted: return

    questions = [
        "Do you often have headaches?",
        "Is your appetite poor?",
        "Do you sleep badly?",
        "Are you easily frightened?",
        "Do your hands shake?",
        "Do you feel nervous, tense or worried?",
        "Is your digestion poor?",
        "Do you have trouble thinking clearly?",
        "Do you feel unhappy?",
        "Do you cry more than usual?",
        "Do you find it difficult to enjoy your daily activities?",
        "Do you find it difficult to make decisions?",
        "Is your daily work suffering?",
        "Are you unable to play a useful part in life?",
        "Have you lost interest in things?",
        "Do you feel that you are a worthless person?",
        "Has the thought of ending your life been on your mind?",
        "Do you feel tired all the time?",
        "Do you have uncomfortable feelings in your stomach?",
        "Are you easily tired?",
        "Do you feel someone has been trying to harm you in some way?",
        "Are you a much more important person than most people think?",
        "Have you noticed any interference or anything else unusual with your thinking?",
        "Do you ever hear voices without knowing where they come from?",
        "Have you had seizures, convulsions, or fits?",
        "Has drink (alcohol) caused problems for you or your family?",
        "Do you smoke cigarettes?",
        "Do you use any other non-medical drugs?",
    ]

    insert_questions(conn, tid, [
        {'key': f'srq_{i+1}', 'label': f"{i+1}. {q}", 'type': 'yes_no',
         'options': ['Yes', 'No'], 'required': True}
        for i, q in enumerate(questions)
    ])
    print(f"  ✓ {name}: {len(questions)} questions seeded (id={tid})")


# ─────────────────────────────────────────────────────────────────────────────
# 2. SRQ-F (Amharic)
# ─────────────────────────────────────────────────────────────────────────────

def seed_srq_amharic(conn):
    name = "መጠይቅ አንድ - የስነ-ልቦና ጤና ደህንነት ምዘና (SRQ-F Amharic)"
    tid, inserted = upsert_template(
        conn, name,
        "ይህ የዓለም ጤና ድርጅት (WHO) መጠይቅ ባለፉት 30 ቀናት ውስጥ ስለነበሩ ስሜቶችና ችግሮች ይጠይቃል። ለእያንዳንዱ ጥያቄ አዎ ወይም አይደለም ይመልሱ።",
        "Mental Health Screening", "SRQ, WHO, Amharic, ስነ-ልቦና, ምዘና",
        "Amharic"
    )
    if not inserted: return

    questions = [
        "ብዙ ጊዜ ራስዎ ይቆጣሉ?",
        "ምግብ መብላት አይፈልጉም?",
        "ጠዋት ሲነሱ ደካማ ስሜት ይሰማሎ?",
        "ቀላሉ ነገር ያስፈራሎ?",
        "እጆችዎ ይንቀጠቀጣሉ?",
        "ነርቭ ይሆናሉ፣ ዘና ማለት ይቸግሮታል ወይም ይጨናነቃሉ?",
        "ምግብ ከምሳ/ከምሽት በኋላ ሆድ ምቾት ይሰጥዎታል?",
        "ሃሳቦን ግልጽ አድርጎ ማስቀመጥ ይቸግሮታል?",
        "አሳዛኝ ስሜት ይሰማሎ?",
        "ከተለመደው በላይ ያለቅሳሉ?",
        "የዕለት ተዕለት ሥራዎን ለመደሰት ይቸገራሉ?",
        "ውሳኔ ለማድረግ ይቸግሮታል?",
        "የዕለት ተዕለት ሥራዎ ተቸጋርቷል?",
        "ጠቃሚ ሚና ለመጫወት አልቻሉም?",
        "ፍላጎትዎ ቀሷል?",
        "ዋጋ የሌለዎ ሰው ነኝ ብለው ያስባሉ?",
        "ሕይወትዎን ለማጥፋት አስበዋል?",
        "ሁልጊዜ ደካሞ ስሜት ይሰማሎ?",
        "ሆዳቸው ምቾት ይሰጥዎታል?",
        "ቀለሙ ይደክሞታል?",
        "አንዳንድ ሰዎች ሊጎዱዎ ሞክረዋል ብለው ያስባሉ?",
        "ከብዙ ሰዎች የምቀልጡ ሰው ነኝ ብለው ያስባሉ?",
        "ሃሳብዎ ላይ ልዩ ልዩ ጣልቃ ገብነት ወይም ሌላ ያልተለመደ ነገር አስተውለዋል?",
        "ምንጩ ሳያውቁ ድምጾች ይሰሙ ነበር?",
        "ኪ.ሮ. (ቁርጠቶችor ሚጡ) ወቅቶች ነበሩ?",
        "አልኮሆል/ጠጅ ለርስዎ ወይም ለቤተሰብዎ ችግር ፈጥሯል?",
        "ሲጃራ ያጨሳሉ?",
        "ሌሎች ዕፆች ወይም ሱስ አምጪ ንጥረ-ነገሮች ይጠቀማሉ?",
    ]

    insert_questions(conn, tid, [
        {'key': f'srq_am_{i+1}', 'label': f"{i+1}. {q}", 'type': 'yes_no',
         'options': ['አዎ', 'አይደለም'], 'required': True}
        for i, q in enumerate(questions)
    ])
    print(f"  ✓ {name}: {len(questions)} questions seeded (id={tid})")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Hopkins Symptom Checklist (HSCL-25)
# ─────────────────────────────────────────────────────────────────────────────

def seed_hopkins(conn):
    name = "Hopkins Symptom Checklist (HSCL-25)"
    tid, inserted = upsert_template(
        conn, name,
        "A 25-item self-report symptom inventory measuring symptoms of anxiety and depression. "
        "Rate how much each problem bothered you during the last 7 days.",
        "Mental Health Screening", "Hopkins, HSCL, anxiety, depression, screening",
        "English"
    )
    if not inserted: return

    options = ["Not at all (1)", "A little bit (2)", "Quite a bit (3)", "Extremely (4)"]

    anxiety_items = [
        "Suddenly scared for no reason",
        "Feeling afraid",
        "Faintness, dizziness, or weakness",
        "Heart pounding or racing",
        "Trembling",
        "Feeling tense or keyed up",
        "Headaches",
        "Feeling restless or can't sit still",
        "Spells of terror or panic",
        "Feeling so restless you couldn't sit still",
    ]

    depression_items = [
        "Feeling low in energy, slowed down",
        "Blaming yourself for things",
        "Crying easily",
        "Feeling of being trapped or caught",
        "Loss of interest in things",
        "Feeling hopeless about the future",
        "Feeling sad",
        "Being bothered by thoughts or feelings",
        "Having no interest in things",
        "Feeling everything is an effort",
        "Feeling worthless",
        "Thoughts of ending your life",
        "Feeling of being lonely",
        "Feeling blue",
        "Worrying too much about things",
    ]

    qs = []
    for i, q in enumerate(anxiety_items):
        qs.append({'key': f'hscl_a{i+1}', 'label': f"ANXIETY {i+1}. {q}",
                   'type': 'single_choice', 'options': options, 'required': True})
    for i, q in enumerate(depression_items):
        qs.append({'key': f'hscl_d{i+1}', 'label': f"DEPRESSION {i+1}. {q}",
                   'type': 'single_choice', 'options': options, 'required': True})

    insert_questions(conn, tid, qs)
    print(f"  ✓ {name}: {len(qs)} questions seeded (id={tid})")


# ─────────────────────────────────────────────────────────────────────────────
# 4. WHOQOL-BREF
# ─────────────────────────────────────────────────────────────────────────────

def seed_whoqol(conn):
    name = "WHOQOL-BREF Quality of Life Assessment"
    tid, inserted = upsert_template(
        conn, name,
        "The WHOQOL-BREF is a 26-item instrument assessing quality of life across four domains: "
        "physical health, psychological, social relationships, and environment.",
        "Quality of Life", "WHOQOL, WHO, quality of life, wellbeing",
        "English"
    )
    if not inserted: return

    options_5 = ["Very Poor", "Poor", "Neither Poor Nor Good", "Good", "Very Good"]
    options_5b = ["Very Dissatisfied", "Dissatisfied", "Neither", "Satisfied", "Very Satisfied"]
    options_5c = ["Not at all", "A little", "A moderate amount", "Very much", "An extreme amount"]
    options_5d = ["Never", "Seldom", "Quite often", "Very often", "Always"]

    questions = [
        ("whoqol_1", "How would you rate your quality of life?", options_5),
        ("whoqol_2", "How satisfied are you with your health?", options_5b),
        ("whoqol_3", "To what extent do you feel that physical pain prevents you from doing what you need to do?", options_5c),
        ("whoqol_4", "How much do you need any medical treatment to function in your daily life?", options_5c),
        ("whoqol_5", "How much do you enjoy life?", options_5c),
        ("whoqol_6", "To what extent do you feel your life to be meaningful?", options_5c),
        ("whoqol_7", "How well are you able to concentrate?", options_5c),
        ("whoqol_8", "How safe do you feel in your daily life?", options_5c),
        ("whoqol_9", "How healthy is your physical environment?", options_5c),
        ("whoqol_10", "Do you have enough energy for everyday life?", options_5d),
        ("whoqol_11", "Are you able to accept your bodily appearance?", options_5d),
        ("whoqol_12", "Have you enough money to meet your needs?", options_5d),
        ("whoqol_13", "How available to you is the information that you need in your day-to-day life?", options_5d),
        ("whoqol_14", "To what extent do you have the opportunity for leisure activities?", options_5d),
        ("whoqol_15", "How well are you able to get around?", options_5),
        ("whoqol_16", "How satisfied are you with your sleep?", options_5b),
        ("whoqol_17", "How satisfied are you with your ability to perform your daily living activities?", options_5b),
        ("whoqol_18", "How satisfied are you with your capacity for work?", options_5b),
        ("whoqol_19", "How satisfied are you with yourself?", options_5b),
        ("whoqol_20", "How satisfied are you with your personal relationships?", options_5b),
        ("whoqol_21", "How satisfied are you with your sex life?", options_5b),
        ("whoqol_22", "How satisfied are you with the support you get from your friends?", options_5b),
        ("whoqol_23", "How satisfied are you with the conditions of your living place?", options_5b),
        ("whoqol_24", "How satisfied are you with your access to health services?", options_5b),
        ("whoqol_25", "How satisfied are you with your transport?", options_5b),
        ("whoqol_26", "How often do you have negative feelings such as blue mood, despair, anxiety, depression?", options_5d),
    ]

    insert_questions(conn, tid, [
        {'key': k, 'label': f"{i+1}. {l}", 'type': 'single_choice', 'options': o, 'required': True}
        for i, (k, l, o) in enumerate(questions)
    ])
    print(f"  ✓ {name}: {len(questions)} questions seeded (id={tid})")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Big Five Personality Test (Amharic)
# ─────────────────────────────────────────────────────────────────────────────

def seed_big_five(conn):
    name = "የስብዕና ምዘና - The Big Five Personality Test (Amharic)"
    tid, inserted = upsert_template(
        conn, name,
        "ይህ ምዘና አምስቱን ዋና ዋና የስብዕና ባሕሪያት (Big Five) ይለካል፡ "
        "Extroversion፣ Agreeableness፣ Conscientiousness፣ Neuroticism፣ Openness to Experience።",
        "Personality", "Big Five, personality, Amharic, ስብዕና",
        "Amharic"
    )
    if not inserted: return

    options = ["በጣም አልስማማም", "አልስማማም", "ትንሽ አልስማማም", "ትንሽ እስማማለሁ", "እስማማለሁ", "በጣም እስማማለሁ"]

    questions = [
        # Extraversion (E) items
        "ብዙ ሰዎች ጋር ሲሆኑ ደስ ይሰኛቸዋል",
        "ቀልጣፋ ናቸው እና ፈጥነው ይሠራሉ",
        "ሃሳባቸውን ለሌሎች ለማካፈል ወደኋላ አይሉም",
        "ሁሌ ሊናገሩ ይወዳሉ",
        "ፓርቲ ወይም ሰዎች ካሉ ቦታ ደስ ይሰኛቸዋል",
        "ሌሎችን ቀና አድርጎ ወደኋላ ሳይሉ ይቀሰቅሳሉ",
        "ሌሎችን ቀና የሚያደርጉ ናቸው",
        "ሰዎች ጋር ሲሆኑ ደስ ይሰኛቸዋል",
        "የሌሎች ሰዎች ሕይወት ላይ ለመሳተፍ ይወዳሉ",
        "ቁምነገር አላቸው፣ ሁሌ ሆዳቸው ፀጥ ሊቀር አይጥሩም",
        # Agreeableness (A) items
        "ሰዎችን ይይዛሉ",
        "ሌሎችን ለሚሰሩ ሥራ ሁሌ ምስጋና ይሰጣሉ",
        "ሰዎችን ለሚሰቃዩ ሲሰሙ ደርደው ይሄዳሉ",
        "ጨዋ ናቸው",
        "ሌሎችን ለሚቸገሩ ይረዳሉ",
        "ሁሌ ሰዎችን ያዳምጣሉ",
        "ስሜቶቻቸውን ሌሎች ያዳምጡ ብለው ይጠብቃሉ",
        "ሰዎች ሁሌ ሊናቁ አይሉም",
        "ሌሎችን ሁሌ ቀና አድርጎ ያዩዋቸዋል",
        "ለሰዎች ሲያደርጉ ዋጋ ሲያጡ ምን ይሰማቸዋል ብሎ ያስባሉ",
        # Conscientiousness (C) items
        "ሙሉ ሰዓት ምንም ሳያባክኑ ይሠራሉ",
        "ቀደም ብሎ ሥራ ያዘጋጃሉ",
        "ዕቅዶቻቸውን ይከተላሉ",
        "ዝቅተኛ ሥራ ብለው አያዙ",
        "ሁሌ ቆጥበው ያስቀምጣሉ",
        "ዝርዝሮችን ሁሌ ያረጋግጣሉ",
        "ትኩረታቸው ሁሌ ዓላማ ላይ ነው",
        "ሥራቸውን ፈጥረው ያጠናቅቃሉ",
        "ዝቅተኛ ሥራ ሳያዙ ሁሌ ዓቅሙን ያደርጋሉ",
        "ሥርዓት ያዙ ናቸው",
        # Neuroticism (N) items
        "ብዙ ጊዜ ይጨናነቃሉ",
        "ቀላሉ ነገር ሳይቀር ያበሳጫቸዋል",
        "ቀላሉ ነገር ያሳዝናቸዋል",
        "ሁሌ ስሜታቸው ሊዋዥቅ ይፈልጋሉ",
        "ቁጣቸው ቀላሉ ነው",
        "ብቻቸውን ሲሆኑ ሌሎች ሊነቅሷቸው ያስባሉ",
        "ብዙ ጊዜ ስሜታቸው ይቀያየራሉ",
        "ሰዎች ሲተቿቸው ቀላሉ ያስፈራቸዋል",
        "ሁሌ ተጨናንቀው ናቸው",
        "ሁሌ ሰዎች ሊሄዱ ያስፈሯቸዋል",
        # Openness (O) items
        "ትኩስ ሃሳብ ሁሌ ወደ አዕምሮዋቸው ይመጣሉ",
        "ብዙ ምናቡ ሊጠቀሙ ይወዳሉ",
        "ሁሌ ለሥነ-ጥበብ ፍቅር አላቸው",
        "ሃሳቦቻቸው ሁሌ ፈጠራ ናቸው",
        "ሁሌ አዲስ ሃሳብ ለሌሎች ያካፍሏቸዋል",
        "ፍልስፍናዊ ሃሳቦች ያስደስቷቸዋል",
        "ሃሳቦቻቸው ሁሌ ሌሎችን ያስደምሟቸዋል",
        "ሙዚቃ ሲሰሙ ስሜቱ ሁሌ ያጥፈዋቸዋል",
        "ሁሌ አዲስ ነገር ሊሞክሩ ይወዳሉ",
        "ፈጠራ ያለ ሥዓሊ ወይም ዘፋኝ ናቸው",
    ]

    insert_questions(conn, tid, [
        {'key': f'bf_{i+1}', 'label': f"{i+1}. {q}", 'type': 'single_choice',
         'options': options, 'required': True}
        for i, q in enumerate(questions)
    ])

    # Add scoring info
    conn.execute(
        """INSERT INTO assessment_questions
           (template_id, question_key, label_en, question_type, required, options_json, sort_order)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            tid,
            'scoring_info',
            "Scoring Guide:\n"
            "E (Extroversion)      = items 1,2,3,4,5,6,7,8,9,10\n"
            "A (Agreeableness)     = items 11,12,13,14,15,16,17,18,19,20\n"
            "C (Conscientiousness) = items 21,22,23,24,25,26,27,28,29,30\n"
            "N (Neuroticism)       = items 31,32,33,34,35,36,37,38,39,40\n"
            "O (Openness)          = items 41,42,43,44,45,46,47,48,49,50\n"
            "Scale: 1=Strongly Disagree ... 6=Strongly Agree",
            'info',
            0,
            None,
            51,
        )
    )
    print(f"  ✓ {name}: {len(questions)} questions seeded (id={tid})")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def seed_all(conn):
    try:
        seed_srq_english(conn)
        seed_srq_amharic(conn)
        seed_hopkins(conn)
        seed_whoqol(conn)
        seed_big_five(conn)
        print("\n✅ All 5 templates seeded successfully.")
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    print("Connecting to database...")
    with _db.connect() as conn:
        print("Connected. Seeding assessment templates...\n")
        seed_all(conn)
