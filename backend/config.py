"""
Configuration file for AstroRemedis backend
Contains hardcoded data structures that can be easily modified
"""

# Follow-up questions for different conversation categories
FOLLOW_UP_QUESTIONS = {
    "career": [
        "Aapka current job role kya hai aur kya aap usse satisfied hain?",
        "Kya aap job change ya promotion ke baare mein soch rahe hain?",
        "Aapke career goals kya hain jo aap achieve karna chahte hain?",
        "Kya aap koi naya business start karna chahte hain?",
        "Aapke field mein kya challenges aa rahe hain?",
        "Kya aapko lagta hai ki aapka talent properly utilize ho raha hai?",
        "Aapke dream job kya hai aur uske liye kya karna hoga?",
        "Kya aapko lagta hai ki aapka current role aapke potential ke saath match karta hai?",
        "Aapke industry mein future prospects kya lagte hain?",
        "Kya aapko lagta hai ki aapka boss aapko appreciate karta hai?",
        "Aapke colleagues ke saath relationship kaise hai?",
        "Kya aapko lagta hai ki aapka work-life balance theek hai?",
        "Aapke field mein kya skills develop karni chahiye?",
        "Kya aapko lagta hai ki aapka current company mein growth hai?",
        "Aapke career mein kya biggest achievement hai ab tak?"
    ],
    "relationship": [
        "Kya aapke rishte ki baat chal rahi hai kya?",
        "Aapki current relationship status kya hai?",
        "Kya aap marriage ke liye ready hain ya koi specific concerns hain?",
        "Aapke family mein koi pressure hai marriage ke liye?",
        "Aapke partner ke saath kya issues hain jo solve karni hain?",
        "Kya aapko lagta hai ki aapka partner aapko samajhta hai?",
        "Aapke relationship mein trust ki situation kaise hai?",
        "Kya aapko lagta hai ki aapka partner aapke dreams ko support karta hai?",
        "Aapke relationship mein communication kaise hai?",
        "Kya aapko lagta hai ki aapka partner aapke family ko pasand karta hai?",
        "Aapke relationship mein kya biggest challenge hai?",
        "Kya aapko lagta hai ki aapka partner aapke career ko support karta hai?",
        "Aapke relationship mein romance kaise hai?",
        "Kya aapko lagta hai ki aapka partner aapke values ke saath match karta hai?",
        "Aapke relationship mein future planning kaise hai?"
    ],
    "health": [
        "Aapko koi specific health issues hain jo aapko pareshan kar rahe hain?",
        "Kya aap regular exercise aur healthy diet follow karte hain?",
        "Aapke family mein koi hereditary health problems hain?",
        "Kya aap stress ya anxiety se deal kar rahe hain?",
        "Aapki sleep pattern kaise hai?",
        "Kya aapko lagta hai ki aapka energy level theek hai?",
        "Aapke daily routine mein kya health activities hain?",
        "Kya aapko lagta hai ki aapka mental health theek hai?",
        "Aapke diet mein kya improvements kar sakte hain?",
        "Kya aapko lagta hai ki aapka work stress aapke health ko affect kar raha hai?",
        "Aapke family mein koi health history hai jo aapko concern karti hai?",
        "Kya aapko lagta hai ki aapka lifestyle healthy hai?",
        "Aapke health goals kya hain jo aap achieve karna chahte hain?",
        "Kya aapko lagta hai ki aapka environment healthy hai?",
        "Aapke health mein kya biggest concern hai?"
    ],
    "general": [
        "Aapke man mein aur kya sawaal hai jiska jawab aap chahte hain?",
        "Kya aap koi specific problem face kar rahe hain jo solve karna chahte hain?",
        "Aapke life mein koi major changes aane wale hain?",
        "Kya aap koi important decision lene wale hain?",
        "Aapke life mein kya biggest challenge hai abhi?",
        "Kya aapko lagta hai ki aapka life mein balance hai?",
        "Aapke family ke saath relationship kaise hai?",
        "Kya aapko lagta hai ki aapka life mein purpose hai?",
        "Aapke friends aur social circle kaise hai?",
        "Kya aapko lagta hai ki aapka life mein happiness hai?",
        "Aapke life mein kya biggest fear hai?",
        "Kya aapko lagta hai ki aapka life mein peace hai?",
        "Aapke life mein kya biggest dream hai?",
        "Kya aapko lagta hai ki aapka life mein growth hai?",
        "Aapke life mein kya biggest regret hai?"
    ]
}

# Question introduction variations
QUESTION_INTROS = [
    "At the very end of your response, gently ask the user this question to continue the flow:",
    "End your response by asking this follow-up question naturally:",
    "Conclude your response with this question to keep the conversation flowing:",
    "Finish your response by asking this question to engage the user further:",
    "End with this question to continue the meaningful conversation:"
]

# Response style to follow-up category mapping
RESPONSE_STYLE_MAP = {
    "relationship_advice": "relationship",
    "career_guidance": "career",
    "health_guidance": "health",
    "child_guidance": "relationship"  # Children questions map to relationship category
}




