"""
seed_assessments_pg.py
Seeds all default assessment templates into the PostgreSQL database via db.py.
Templates: SRQ-F (EN), SRQ-F (AM), Hopkins SCL-58, WHOQOL-BREF, Big Five (AM)
"""
import json
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db as _db

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def upsert_template(conn, name, description, category, tags, lang, created_by=1):
    """Return (template_id, inserted). Skip if already exists."""
    row = conn.execute(
        "SELECT id FROM assessment_templates WHERE name = %s", (name,)
    ).fetchone()
    if row:
        print(f"  already exists: '{name}' (id={row['id']})")
        return row['id'], False
    cur = conn.execute(
        """INSERT INTO assessment_templates
           (name, description, form_language, is_public, is_active,
            created_by, published, category, tags)
           VALUES (%s, %s, %s, 1, 1, %s, 1, %s, %s)
           RETURNING id""",
        (name, description, lang, created_by, category, tags)
    )
    return cur.fetchone()['id'], True


def insert_questions(conn, template_id, questions):
    """
    questions: list of dicts with keys:
      key, label, type ('yes_no'|'single_choice'|'info'), options (list|None), required
    """
    for i, q in enumerate(questions):
        opts = json.dumps(q.get('options') or [], ensure_ascii=False) \
               if q.get('options') else None
        conn.execute(
            """INSERT INTO assessment_questions
               (template_id, question_key, label_en, question_type,
                required, options_json, sort_order)
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


def drop_template(conn, name):
    """Remove a template and its questions if it exists."""
    row = conn.execute(
        "SELECT id FROM assessment_templates WHERE name = %s", (name,)
    ).fetchone()
    if row:
        conn.execute(
            "DELETE FROM assessment_questions WHERE template_id = %s", (row['id'],)
        )
        conn.execute(
            "DELETE FROM assessment_templates WHERE id = %s", (row['id'],)
        )
        print(f"  removed old: '{name}'")


# ---------------------------------------------------------------------------
# 1. SRQ-F English
# ---------------------------------------------------------------------------

def seed_srq_english(conn):
    name = "Self-Reporting Questionnaire (SRQ-F) - English"
    tid, ok = upsert_template(
        conn, name,
        "The SRQ is a WHO tool to screen for neurotic disorders. "
        "Answer Yes or No for each item based on the last 30 days.",
        "Mental Health Screening", "SRQ, WHO, screening, mental health", "English"
    )
    if not ok:
        return
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
        {'key': f'srq_{i+1}', 'label': f"{i+1}. {q}",
         'type': 'yes_no', 'options': ['Yes', 'No'], 'required': True}
        for i, q in enumerate(questions)
    ])
    print(f"  seeded: {name} ({len(questions)} questions)")


# ---------------------------------------------------------------------------
# 2. SRQ-F Amharic
# ---------------------------------------------------------------------------

def seed_srq_amharic(conn):
    name = "SRQ-F Amharic - መጠይቅ አንድ (የስነ-ልቦና ጤና ደህንነት ምዘና)"
    tid, ok = upsert_template(
        conn, name,
        "ይህ የዓለም ጤና ድርጅት (WHO) መጠይቅ ባለፉት 30 ቀናት ውስጥ ስለነበሩ ስሜቶችና "
        "ችግሮች ይጠይቃል። ለእያንዳንዱ ጥያቄ አዎ ወይም አይደለም ይመልሱ።",
        "Mental Health Screening", "SRQ, WHO, Amharic, ስነ-ልቦና, ምዘና", "Amharic"
    )
    if not ok:
        return
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
        "ቁርጠቶች ወቅቶች ነበሩ?",
        "አልኮሆል/ጠጅ ለርስዎ ወይም ለቤተሰብዎ ችግር ፈጥሯል?",
        "ሲጃራ ያጨሳሉ?",
        "ሌሎች ዕፆች ወይም ሱስ አምጪ ንጥረ-ነገሮች ይጠቀማሉ?",
    ]
    insert_questions(conn, tid, [
        {'key': f'srq_am_{i+1}', 'label': f"{i+1}. {q}",
         'type': 'yes_no', 'options': ['አዎ', 'አይደለም'], 'required': True}
        for i, q in enumerate(questions)
    ])
    print(f"  seeded: {name} ({len(questions)} questions)")


# ---------------------------------------------------------------------------
# 3. Hopkins Symptom Checklist (SCL-58)
# ---------------------------------------------------------------------------

def seed_hopkins(conn):
    # Remove old HSCL-25 if it exists
    drop_template(conn, "Hopkins Symptom Checklist (HSCL-25)")

    name = "Hopkins Symptom Checklist (SCL-58)"
    tid, ok = upsert_template(
        conn, name,
        "A 58-item self-report symptom inventory. Rate how much each problem has bothered you "
        "during the last 7 days, including today. "
        "Scale: 1=Not at all, 2=A little bit, 3=Quite a bit, 4=Extremely.",
        "Mental Health Screening", "Hopkins, SCL, SCL-58, anxiety, depression, screening",
        "English"
    )
    if not ok:
        return
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
    print(f"  seeded: {name} ({len(items)} questions)")


# ---------------------------------------------------------------------------
# 4. WHOQOL-BREF (official scales with reverse-coded items)
# ---------------------------------------------------------------------------

def seed_whoqol(conn):
    name = "WHOQOL-BREF Quality of Life Assessment"
    tid, ok = upsert_template(
        conn, name,
        "The WHOQOL-BREF is a 26-item instrument assessing quality of life across four domains: "
        "Physical Health (Domain 1), Psychological (Domain 2), Social Relationships (Domain 3), "
        "and Environment (Domain 4). Think about your life in the last four weeks.",
        "Quality of Life", "WHOQOL, WHO, quality of life, wellbeing", "English"
    )
    if not ok:
        return

    qual     = ["1 - Very poor", "2 - Poor", "3 - Neither poor nor good", "4 - Good", "5 - Very good"]
    sat      = ["1 - Very dissatisfied", "2 - Dissatisfied", "3 - Neither satisfied nor dissatisfied",
                "4 - Satisfied", "5 - Very satisfied"]
    extent   = ["1 - Not at all", "2 - A little", "3 - A moderate amount", "4 - Very much", "5 - An extreme amount"]
    ext_rev  = ["5 - Not at all", "4 - A little", "3 - A moderate amount", "2 - Very much", "1 - An extreme amount"]
    complete = ["1 - Not at all", "2 - A little", "3 - Moderately", "4 - Mostly", "5 - Completely"]
    freq_rev = ["5 - Never", "4 - Seldom", "3 - Quite often", "2 - Very often", "1 - Always"]

    questions = [
        ("whoqol_1",  "How would you rate your quality of life?",                                                         qual),
        ("whoqol_2",  "How satisfied are you with your health?",                                                          sat),
        ("whoqol_3",  "To what extent do you feel that physical pain prevents you from doing what you need to do?",       ext_rev),
        ("whoqol_4",  "How much do you need any medical treatment to function in your daily life?",                       ext_rev),
        ("whoqol_5",  "How much do you enjoy life?",                                                                      extent),
        ("whoqol_6",  "To what extent do you feel your life to be meaningful?",                                           extent),
        ("whoqol_7",  "How well are you able to concentrate?",                                                            extent),
        ("whoqol_8",  "How safe do you feel in your daily life?",                                                         extent),
        ("whoqol_9",  "How healthy is your physical environment?",                                                        extent),
        ("whoqol_10", "Do you have enough energy for everyday life?",                                                     complete),
        ("whoqol_11", "Are you able to accept your bodily appearance?",                                                   complete),
        ("whoqol_12", "Have you enough money to meet your needs?",                                                        complete),
        ("whoqol_13", "How available to you is the information that you need in your day-to-day life?",                   complete),
        ("whoqol_14", "To what extent do you have the opportunity for leisure activities?",                               complete),
        ("whoqol_15", "How well are you able to get around?",                                                             qual),
        ("whoqol_16", "How satisfied are you with your sleep?",                                                           sat),
        ("whoqol_17", "How satisfied are you with your ability to perform your daily living activities?",                 sat),
        ("whoqol_18", "How satisfied are you with your capacity for work?",                                               sat),
        ("whoqol_19", "How satisfied are you with yourself?",                                                             sat),
        ("whoqol_20", "How satisfied are you with your personal relationships?",                                          sat),
        ("whoqol_21", "How satisfied are you with your sex life?",                                                        sat),
        ("whoqol_22", "How satisfied are you with the support you get from your friends?",                                sat),
        ("whoqol_23", "How satisfied are you with the conditions of your living place?",                                  sat),
        ("whoqol_24", "How satisfied are you with your access to health services?",                                       sat),
        ("whoqol_25", "How satisfied are you with your transport?",                                                       sat),
        ("whoqol_26", "How often do you have negative feelings such as blue mood, despair, anxiety, depression?",         freq_rev),
    ]
    insert_questions(conn, tid, [
        {'key': k, 'label': f"{i+1}. {l}", 'type': 'single_choice', 'options': o, 'required': True}
        for i, (k, l, o) in enumerate(questions)
    ])
    # Scoring guide
    conn.execute(
        """INSERT INTO assessment_questions
           (template_id, question_key, label_en, question_type, required, options_json, sort_order)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (tid, 'whoqol_scoring',
         "SCORING GUIDE\n"
         "Domain 1 - Physical Health (Q3,Q4,Q10,Q15,Q16,Q17,Q18):\n"
         "  Raw = (6-Q3) + (6-Q4) + Q10 + Q15 + Q16 + Q17 + Q18\n\n"
         "Domain 2 - Psychological (Q5,Q6,Q7,Q11,Q19,Q26):\n"
         "  Raw = Q5 + Q6 + Q7 + Q11 + Q19 + (6-Q26)\n\n"
         "Domain 3 - Social Relationships (Q20,Q21,Q22):\n"
         "  Raw = Q20 + Q21 + Q22\n\n"
         "Domain 4 - Environment (Q8,Q9,Q12,Q13,Q14,Q23,Q24,Q25):\n"
         "  Raw = Q8 + Q9 + Q12 + Q13 + Q14 + Q23 + Q24 + Q25\n\n"
         "Transform to 0-100: score = (raw - 4) / (4*n) * 100\n"
         "  where n = number of items in the domain",
         'info', 0, None, 27)
    )
    print(f"  seeded: {name} ({len(questions)} questions + scoring guide)")


# ---------------------------------------------------------------------------
# 5. Big Five Personality Test (Amharic) - Aha Psychological Service version
# ---------------------------------------------------------------------------

def seed_big_five(conn):
    # Clean up previous versions under old names
    for old_name in [
        "የስብዕና ምዘና - The Big Five Personality Test (Amharic)",
        "Big Five Personality Test - አሃ ስነ-ልቦና (Amharic)"
    ]:
        drop_template(conn, old_name)

    name = "Big Five Personality Test - አሃ ስነ-ልቦና (Amharic)"
    tid, ok = upsert_template(
        conn, name,
        "የሰውን ልጅ ማንነት ለመለካት ከሚያገለግሉ የተለያዩ መመዘኛዎች መካከል 'The Big Five Personality Test' አንዱ ነው። "
        "በእያንዳንዱ ጉዳይ ላይ እራስዎን በመገምገም ከተሰጡት አማራጮች ይገልፀኛል የሚሉትን ወይንም የሚስማሙበትን "
        "መጠን ያመልክቱ። (አሃ ስነ-ልቦና አገልግሎት ድርጅት)",
        "Personality", "Big Five, personality, Amharic, ስብዕና, አሃ", "Amharic"
    )
    if not ok:
        return

    # Official 5-point scale from the Aha document
    options = [
        "1 - አልስማማም",
        "2 - በመጠኑ አልስማማም",
        "3 - መወሰን ይከብደኛል",
        "4 - በመጠኑ እስማማለሁ",
        "5 - እስማማለሁ",
    ]

    # Exact 50 items from the Aha Psychological Service document
    questions = [
        "በጓደኞቼ መካከል ወሳኝ ነኝ",
        "ለሌሎች ሰዎች ብዙም ትኩረት አልሰጥም",
        "ሁሌም ዝግጁ ነኝ",
        "በነገሮች በቀላሉ እጨናነቃለሁ",
        "ብዙ ቃላትን አውቃለሁ",
        "ብዙ አላወራም",
        "ከሰዎች ጋር መሆን ያስደስተኛል",
        "መገልገያዎቼን መያዝ እረሳለሁ",
        "ብዙ ጊዜ ዘና የማለት ስሜት አለኝ",
        "ረቂቅ ሃሳቦችን የመረዳት ችግር አለብኝ",
        "በሰዎች መካከል መሆን ምቾት ይሰጠኛል",
        "ሰዎችን የሚያስከፋ ነገር እናገራለሁ",
        "ለዝርዝር ጉዳዮች ትኩረት እሰጣለሁ",
        "ስለነገሮች እጨነቃሁ",
        "ለነገሮች ግልፅ የአእምሮ ምስል አለኝ",
        "ወጥ ባህሪ አለኝ",
        "የሌሎች ሰዎች ሃዘን ያሳዝነኛል",
        "ነገሮችን ሆን ብዬ አዘበራርቃለሁ",
        "አልፎ አልፎ ይደብረኛል",
        "ረቂቅ ለሆኑ ሃሳቦች ፍላጎት የለኝም",
        "ንግግር የመጀመር ልምድ አለኝ",
        "ለሌሎች ሰዎች ችግሮች ፍላጎት የለኝም",
        "አሰልቺ ስራዎችን በቶሎ አከናውናለሁ",
        "በቀላሉ እረበሻለሁ",
        "በጣም ጥሩ ሃሳቦች አሉኝ",
        "በመጠኑ መናገር እመርጣለሁ",
        "ይቅር-ባይ ልብ አለኝ",
        "ብዙ ጊዜ ነገሮችን ወደቦታቸው መመለስ እረሳለሁ",
        "በቀላሉ እበሳጫለሁ",
        "ጥሩ በአዕምሮ የመሳል ችሎታ የለኝም",
        "በድግሶች ላይ ከተለያዩ ሰዎች ጋር አወራለሁ",
        "ከሌሎች ጋር የመሆን ፍላጎት የለኝም",
        "ነገሮች እስትክክል ሲሆኑ እወዳለሁ",
        "ብዙ ጊዜ ስሜቴ ይለዋወጣል",
        "ነገሮች በፍጥነት መረዳት እችላለሁ",
        "የሰዎችን ትኩረት መሳብ አልወድም",
        "ለሌሎች ሰዎች ስል ጊዜ እሰጣለሁ",
        "የሚጠበቅብኝን ተግባር አላከናውንም",
        "በርካታ የስሜት መለዋወጥ አለኝ",
        "ከባባድ ቃላትን እጠቀማለሁ",
        "የሰዎችን ትኩረት ማግኘት አያስጨንቀኝም",
        "የሌሎች ሰዎች ስሜት ይሰማኛል",
        "ወጥ የጊዜ አጠቃቀም እከተላለሁ",
        "በቀላሉ ይከፋኛል",
        "ስለነገሮች ያለኝን አመለካከት ለመግለፅ ጊዜ እመድባለሁ",
        "በአዳዲስ ሰዎች መካከል እገኛለሁ",
        "ሰዎች ዘና እንዲሉ አደርጋለሁ",
        "ለምስራው ስራ ከፍተኛ ጥንቃቄ አደርጋለሁ",
        "ብዙውን ጊዜ ይደብረኛል",
        "በርካታ ሃሳቦችን አመነጫለሁ",
    ]

    insert_questions(conn, tid, [
        {'key': f'bf_{i+1}', 'label': f"{i+1}. {q}",
         'type': 'single_choice', 'options': options, 'required': True}
        for i, q in enumerate(questions)
    ])

    # Scoring guide with official formulas
    conn.execute(
        """INSERT INTO assessment_questions
           (template_id, question_key, label_en, question_type, required, options_json, sort_order)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (tid, 'bf_scoring',
         "SCORING GUIDE (scores should be between 0 and 40)\n\n"
         "E (Extroversion)      = 20 + (1) - (6) + (11) - (16) + (21) - (26) + (31) - (36) + (41) - (46)\n"
         "A (Agreeableness)     = 14 - (2) + (7) - (12) + (17) - (22) + (27) - (32) + (37) + (42) + (47)\n"
         "C (Conscientiousness) = 14 + (3) - (8) + (13) - (18) + (23) - (28) + (33) - (38) + (43) + (48)\n"
         "N (Neuroticism)       = 38 - (4) + (9) - (14) + (19) - (24) - (29) - (34) - (39) - (44) - (49)\n"
         "O (Openness)          =  8 + (5) - (10) + (15) - (20) + (25) - (30) + (35) + (40) + (45) + (50)\n\n"
         "TRAIT DESCRIPTIONS:\n"
         "Extroversion (E): High scorers tend to be very social; Low scorers prefer to work alone.\n"
         "Agreeableness (A): High scorers are typically polite and like people; Low scorers tend to 'tell it like it is'.\n"
         "Conscientiousness (C): High scorers tend to follow rules and prefer clean homes; Low scorers may be messy.\n"
         "Neuroticism (N): The personality trait of being emotional.\n"
         "Openness to Experience (O): High scorers are imaginative and creative; Low scorers are conventional.",
         'info', 0, None, 51)
    )
    print(f"  seeded: {name} ({len(questions)} questions + scoring guide)")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

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
