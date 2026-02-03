"""
FAQ Quick Link Matcher
-----------------------
This utility helps identify high-traffic questions and bypass RAG retrieval
for instant, accurate responses.

Usage:
    from faq_matcher import match_faq_quick_link
    
    user_query = "Where is the campus map?"
    quick_link = match_faq_quick_link(user_query, threshold=0.85)
    if quick_link:
        print(f"Direct link: {quick_link['url']}")
"""

from difflib import SequenceMatcher

# FAQ Quick Links Index (sync with scraper.py)
FAQ_LINKS = {
    "map": {
        "url": "https://www.nku.edu/map",
        "title": "NKU Campus Map",
        "keywords": ["map", "building", "parking", "location", "directions", "where is"],
        "description": "Interactive campus map showing buildings, parking, and directions"
    },
    "canvas": {
        "url": "https://www.nku.edu/mynku",
        "title": "MyNKU Student Portal",
        "keywords": ["canvas", "login", "mynku", "portal", "student login", "sign in"],
        "description": "Student portal access for Canvas, email, and university services"
    },
    "tuition": {
        "url": "https://www.nku.edu/financialaid",
        "title": "Financial Aid & Tuition",
        "keywords": ["tuition", "fafsa", "cost", "financial aid", "payment", "how much"],
        "description": "Information about tuition costs, financial aid, and FAFSA"
    },
    "registrar": {
        "url": "https://www.nku.edu/registrar",
        "title": "Registrar's Office",
        "keywords": ["registrar", "registration", "transcript", "grades", "enroll", "get my transcript"],
        "description": "Registration, transcripts, grades, and academic records"
    },
    "calendar": {
        "url": "https://www.nku.edu/calendar",
        "title": "Academic Calendar",
        "keywords": ["calendar", "dates", "deadlines", "semester", "when", "schedule"],
        "description": "Important dates, deadlines, and academic calendar"
    },
}


def calculate_similarity(text1, text2):
    """Calculate similarity ratio between two text strings."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def match_faq_quick_link(user_query, threshold=0.4):
    """
    Match user query against FAQ quick links.
    
    Args:
        user_query (str): The user's question
        threshold (float): Minimum similarity score (0-1) to return a match
        
    Returns:
        dict or None: FAQ info if match found, None otherwise
    """
    query_lower = user_query.lower()
    best_match = None
    best_score = 0
    
    for category, faq_info in FAQ_LINKS.items():
        # Check for keyword matches (substring matching)
        for keyword in faq_info["keywords"]:
            # Direct substring match gets high score
            if keyword in query_lower:
                # Calculate score based on keyword length vs query length
                # Longer keywords get higher scores
                keyword_score = len(keyword) / max(len(query_lower), len(keyword))
                # Boost score if it's an exact word match
                if f" {keyword} " in f" {query_lower} " or query_lower.startswith(keyword) or query_lower.endswith(keyword):
                    keyword_score += 0.3
                
                if keyword_score > best_score:
                    best_score = min(keyword_score, 1.0)  # Cap at 1.0
                    best_match = {
                        "category": category,
                        "url": faq_info["url"],
                        "title": faq_info["title"],
                        "description": faq_info["description"],
                        "confidence": best_score
                    }
    
    # Return match only if it exceeds threshold
    if best_score >= threshold:
        return best_match
    
    return None



def format_quick_link_response(faq_match):
    """
    Format a quick link response for the chatbot.
    
    Args:
        faq_match (dict): FAQ match from match_faq_quick_link()
        
    Returns:
        str: Formatted markdown response
    """
    return f"""**Quick Answer:**

{faq_match['description']}

**[Visit {faq_match['title']}]({faq_match['url']})**

*This is a high-confidence direct link (confidence: {faq_match['confidence']:.0%})*
"""


# Example usage
if __name__ == "__main__":
    test_queries = [
        "Where is the campus map?",
        "How do I login to Canvas?",
        "What's the tuition cost?",
        "When is the registration deadline?",
        "How do I get my transcript?",
        "Tell me about admission requirements",  # Should NOT match (low similarity)
    ]
    
    print("FAQ Quick Link Matcher - Test Results")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        match = match_faq_quick_link(query, threshold=0.4)  # Lowered threshold
        
        if match:
            print(f"MATCH: {match['title']} ({match['confidence']:.0%} confidence)")
            print(f"  URL: {match['url']}")
        else:
            print("No quick link match - will use RAG retrieval")

