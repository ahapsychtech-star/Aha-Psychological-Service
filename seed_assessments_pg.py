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
# 3. Hopkins Symptom Checklist (SCL-58)
# ─────────────────────────────────────────────────────────────────────────────

def seed_hopkins(conn):
    # Delete old HSCL-25 entry if it exists, then create the full 58-item SCL
    for old_name in ["Hopkins Symptom Checklist (HSCL-25)"]:
        old = conn.execute("SELECT id FROM assessment_templates WHERE name = %s", (old_name,)).fetchone()
        if old:
            conn.execute("DELETE FROM assessment_questions WHERE template_id = %s", (old['id'],))
            conn.execute("DELETE FROM assessment_templates WHERE id = %s", (old['id'],))
            print(f"  ↳ Removed old '{old_name}'")

    name = "Hopkins Symptom Checklist (SCL-58)"
    tid, inserted = upsert_template(
        conn, name,
        "A 58-item self-report symptom inventory. Rate how much each problem has bothered you "
        "during the last 7 days, including today. Scale: 1=Not at all, 2=A little bit, "
        "3=Quite a bit, 4=Extremely.",
        "Mental Health Screening", "Hopkins, SCL, SCL-58, anxiety, depression, screening",
        "English"
    )
    if not inserted: return

    options = ["1 - Not at all", "2 - A little bit", "3 - Quite a bit", "4 - Extremely"]

    items = [
        "Headaches",
        "Nervousness or shakiness inside",
        "Being unable to get rid of bad thoughts or ideas",
        "Faintness or dizziness",
        "Loss of sexual interest or pleasure",
        "Feeling critical of others",
        "Bad dreams",
        "Difficulty in speaking when you are excited",
        "Trouble remembering things",
        "Worried about sloppiness or carelessness",
        "Feeling easily annoyed or irritated",
        "Pains in the heart or chest",
        "Itching",
        "Feeling low in energy or slowed down",
        "Thoughts of ending your life",
        "Sweating",
        "Trembling",
        "Feeling confused",
        "Poor appetite",
        "Crying easily",
        "Feeling shy or uneasy with the opposite sex",
        "A feeling of being trapped or caught",
        "Suddenly scared for no reason",
        "Temper outbursts you could not control",
        "Constipation",
        "Blaming yourself for things",
        "Pains in the lower part of your back",
        "Feeling blocked in getting things done",
        "Feeling lonely",
        "Feeling blue",
        "Worrying too much about things",
        "Feeling no interest in things",
        "Feeling fearful",
        "Your feelings being easily hurt",
        "Having to ask others what you should do",
        "Feeling others do not understand you or are unsympathetic",
        "Feeling that people are unfriendly or dislike you",
        "Having to do things very slowly to ensure correctness",
        "Heart pounding or racing",
        "Nausea or upset stomach",
        "Feeling inferior to others",
        "Soreness of your muscles",
        "Loose bowel movements",
        "Trouble falling asleep",
        "Having to check and double check what you do",
        "Difficulty making decisions",
        "Wanting to be alone",
        "Trouble getting your breath",
        "Hot or cold spells",
        "Having to avoid certain things, places or activities because they frighten you",
        "Your mind going blank",
        "Numbness or tingling in parts of your body",
        "A lump in your throat",
        "Feeling hopeless about the future",
        "Trouble concentrating",
        "Feeling weak in parts of your body",
        "Feeling tense or keyed up",
        "Heavy feelings in your arms or legs",
    ]

    insert_questions(conn, tid, [
        {'key': f'scl_{i+1}', 'label': f"{i+1}. {q}",
         'type': 'single_choice', 'options': options, 'required': True}
        for i, q in enumerate(items)
    ])
    print(f"  ✓ {name}: {len(items)} questions seeded (id={tid})")



# ─────────────────────────────────────────────────────────────────────────────
# 4. WHOQOL-BREF (official version with correct scales per question)
# ─────────────────────────────────────────────────────────────────────────────

def seed_whoqol(conn):
    name = "WHOQOL-BREF Quality of Life Assessment"
    tid, inserted = upsert_template(
        conn, name,
        "The WHOQOL-BREF is a 26-item instrument assessing quality of life across four domains: "
        "Physical Health (Domain 1), Psychological (Domain 2), Social Relationships (Domain 3), "
        "and Environment (Domain 4). Think about your life in the last four weeks.",
        "Quality of Life", "WHOQOL, WHO, quality of life, wellbeing",
        "English"
    )
    if not inserted: return

    # Official WHOQOL-BREF response scales
    qual_scale   = ["1 - Very poor", "2 - Poor", "3 - Neither poor nor good", "4 - Good", "5 - Very good"]
    sat_scale    = ["1 - Very dissatisfied", "2 - Dissatisfied", "3 - Neither satisfied nor dissatisfied", "4 - Satisfied", "5 - Very satisfied"]
    extent_scale = ["1 - Not at all", "2 - A little", "3 - A moderate amount", "4 - Very much", "5 - An extreme amount"]
    # Reverse-coded extent scale (higher = better for pain/treatment need)
    extent_rev   = ["5 - Not at all", "4 - A little", "3 - A moderate amount", "2 - Very much", "1 - An extreme amount"]
    complete_scale = ["1 - Not at all", "2 - A little", "3 - Moderately", "4 - Mostly", "5 - Completely"]
    freq_rev     = ["5 - Never", "4 - Seldom", "3 - Quite often", "2 - Very often", "1 - Always"]

    questions = [
        # Q1 - Overall QoL
        ("whoqol_1",  "How would you rate your quality of life?", qual_scale),
        # Q2 - Health satisfaction
        ("whoqol_2",  "How satisfied are you with your health?", sat_scale),
        # Q3 - Physical pain (reverse: high pain = low QoL)
        ("whoqol_3",  "To what extent do you feel that physical pain prevents you from doing what you need to do?", extent_rev),
        # Q4 - Medical treatment dependence (reverse)
        ("whoqol_4",  "How much do you need any medical treatment to function in your daily life?", extent_rev),
        # Q5
        ("whoqol_5",  "How much do you enjoy life?", extent_scale),
        # Q6
        ("whoqol_6",  "To what extent do you feel your life to be meaningful?", extent_scale),
        # Q7
        ("whoqol_7",  "How well are you able to concentrate?", extent_scale),
        # Q8
        ("whoqol_8",  "How safe do you feel in your daily life?", extent_scale),
        # Q9
        ("whoqol_9",  "How healthy is your physical environment?", extent_scale),
        # Q10
        ("whoqol_10", "Do you have enough energy for everyday life?", complete_scale),
        # Q11
        ("whoqol_11", "Are you able to accept your bodily appearance?", complete_scale),
        # Q12
        ("whoqol_12", "Have you enough money to meet your needs?", complete_scale),
        # Q13
        ("whoqol_13", "How available to you is the information that you need in your day-to-day life?", complete_scale),
        # Q14
        ("whoqol_14", "To what extent do you have the opportunity for leisure activities?", complete_scale),
        # Q15
        ("whoqol_15", "How well are you able to get around?", qual_scale),
        # Q16
        ("whoqol_16", "How satisfied are you with your sleep?", sat_scale),
        # Q17
        ("whoqol_17", "How satisfied are you with your ability to perform your daily living activities?", sat_scale),
        # Q18
        ("whoqol_18", "How satisfied are you with your capacity for work?", sat_scale),
        # Q19
        ("whoqol_19", "How satisfied are you with yourself?", sat_scale),
        # Q20
        ("whoqol_20", "How satisfied are you with your personal relationships?", sat_scale),
        # Q21
        ("whoqol_21", "How satisfied are you with your sex life?", sat_scale),
        # Q22
        ("whoqol_22", "How satisfied are you with the support you get from your friends?", sat_scale),
        # Q23
        ("whoqol_23", "How satisfied are you with the conditions of your living place?", sat_scale),
        # Q24
        ("whoqol_24", "How satisfied are you with your access to health services?", sat_scale),
        # Q25
        ("whoqol_25", "How satisfied are you with your transport?", sat_scale),
        # Q26 - Negative feelings (reverse: frequent = low QoL)
        ("whoqol_26", "How often do you have negative feelings such as blue mood, despair, anxiety, depression?", freq_rev),
    ]

    insert_questions(conn, tid, [
        {'key': k, 'label': f"{i+1}. {l}", 'type': 'single_choice', 'options': o, 'required': True}
        for i, (k, l, o) in enumerate(questions)
    ])

    # Add scoring guide as an informational question
    conn.execute(
        """INSERT INTO assessment_questions
           (template_id, question_key, label_en, question_type, required, options_json, sort_order)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            tid, 'whoqol_scoring',
            "SCORING GUIDE\n"
            "Domain 1 - Physical Health (Q3,Q4,Q10,Q15,Q16,Q17,Q18):\n"
            "  Raw = (6-Q3) + (6-Q4) + Q10 + Q15 + Q16 + Q17 + Q18\n\n"
            "Domain 2 - Psychological (Q5,Q6,Q7,Q11,Q19,Q26):\n"
            "  Raw = Q5 + Q6 + Q7 + Q11 + Q19 + (6-Q26)\n\n"
            "Domain 3 - Social Relationships (Q20,Q21,Q22):\n"
            "  Raw = Q20 + Q21 + Q22\n\n"
            "Domain 4 - Environment (Q8,Q9,Q12,Q13,Q14,Q23,Q24,Q25):\n"
            "  Raw = Q8 + Q9 + Q12 + Q13 + Q14 + Q23 + Q24 + Q25\n\n"
            "Transform to 0-100 scale: score = (raw - 4) / (4*n) * 100\n"
            "  where n = number of items in the domain",
            'info', 0, None, 27
        )
    )
    print(f"  ✓ {name}: {len(questions)} questions + scoring guide seeded (id={tid})")


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
