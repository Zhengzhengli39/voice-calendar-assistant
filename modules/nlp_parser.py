"""
Natural Language Processing module for parsing calendar requests
"""

import re
import dateparser
from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger(__name__)

class NLPParser:
    def __init__(self):
        """Initialize NLP parser"""
        self.timezone = pytz.timezone('UTC')  # Default timezone
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Compile regex patterns for parsing"""
        # Date patterns
        self.date_patterns = [
            r'(today|tonight|this evening)',
            r'(tomorrow|tomorrow morning|tomorrow afternoon|tomorrow evening)',
            r'(day after tomorrow)',
            r'(next week|next month|next year)',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        ]
        
        # Time patterns
        self.time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?',
            r'(\d{1,2})\s*(am|pm|AM|PM)',
            r'(morning|afternoon|evening|night)',
            r'(noon|midnight)',
        ]
        
        # Duration patterns
        self.duration_patterns = [
            r'for\s+(\d+)\s*(hour|hours|hr|hrs|minute|minutes|min|mins)',
            r'from\s+.+\s+to\s+.+',
            r'(\d+)\s*(hour|hours|hr|hrs)\s*and\s*(\d+)\s*(minute|minutes|min|mins)',
        ]
        
        # Combined patterns
        self.date_time_pattern = re.compile(
            r'(' + '|'.join(self.date_patterns) + r')\s+(' + '|'.join(self.time_patterns) + r')',
            re.IGNORECASE
        )
        
    def parse_calendar_request(self, text):
        """
        Parse natural language text to extract calendar event details
        
        Args:
            text: Natural language text containing event information
            
        Returns:
            dict: Parsed event details or None if parsing fails
        """
        try:
            logger.info(f"Parsing text: {text}")
            
            # Initialize result dictionary
            result = {
                'title': '',
                'date': '',
                'start_time': '',
                'end_time': '',
                'duration_minutes': 60,  # Default 1 hour
                'raw_text': text
            }
            
            # Extract event title (remove date/time patterns)
            title = text
            title = re.sub(r'(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?', '', title, flags=re.IGNORECASE)
            title = re.sub(r'(\d{1,2})\s*(am|pm|AM|PM)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'(january|february|march|april|may|june|july|august|september|october|november|december)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'(morning|afternoon|evening|night)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s+', ' ', title).strip()
            
            # Clean up common phrases
            common_phrases = [
                'add to my calendar',
                'schedule a meeting',
                'create an event',
                'set up a meeting',
                'book a time',
                'make an appointment',
                'on my calendar',
                'in google calendar'
            ]
            
            for phrase in common_phrases:
                title = title.replace(phrase, '').replace(phrase.upper(), '')
            
            result['title'] = title.strip() if title.strip() else 'Meeting'
            
            # Parse date
            date_match = self._extract_date(text)
            if date_match:
                result['date'] = date_match.strftime('%Y-%m-%d')
            
            # Parse time
            time_matches = self._extract_time(text)
            if len(time_matches) >= 2:
                result['start_time'] = time_matches[0]
                result['end_time'] = time_matches[1]
            elif len(time_matches) == 1:
                result['start_time'] = time_matches[0]
                # Calculate end time (default 1 hour later)
                end_time = self._calculate_end_time(time_matches[0], result['duration_minutes'])
                result['end_time'] = end_time
            
            # Parse duration
            duration = self._extract_duration(text)
            if duration:
                result['duration_minutes'] = duration
                # Update end time if only start time was provided
                if result['start_time'] and not result['end_time']:
                    result['end_time'] = self._calculate_end_time(result['start_time'], duration)
            
            # Validate required fields
            if not result['date'] or not result['start_time']:
                logger.warning(f"Incomplete parsing: {result}")
                return None
            
            logger.info(f"Successfully parsed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing text: {str(e)}")
            return None
    
    def _extract_date(self, text):
        """Extract date from text"""
        try:
            # Try dateparser first
            parsed_date = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
            if parsed_date:
                return parsed_date.date()
            
            # Fallback to regex patterns
            today = datetime.now().date()
            
            if re.search(r'\btoday\b', text, re.IGNORECASE):
                return today
            elif re.search(r'\btomorrow\b', text, re.IGNORECASE):
                return today + timedelta(days=1)
            elif re.search(r'\bday after tomorrow\b', text, re.IGNORECASE):
                return today + timedelta(days=2)
            
            # Check for day of week
            days = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            for day_name, day_offset in days.items():
                if re.search(r'\b' + day_name + r'\b', text, re.IGNORECASE):
                    current_day = today.weekday()
                    days_ahead = day_offset - current_day
                    if days_ahead <= 0:
                        days_ahead += 7
                    return today + timedelta(days=days_ahead)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting date: {str(e)}")
            return None
    
    def _extract_time(self, text):
        """Extract time from text"""
        times = []
        
        # Pattern for 12-hour format with AM/PM
        pattern_12hr = r'(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?'
        matches = re.findall(pattern_12hr, text, re.IGNORECASE)
        
        for hour, minute, period in matches:
            hour = int(hour)
            minute = int(minute)
            
            # Convert to 24-hour format
            if period and period.lower() == 'pm' and hour < 12:
                hour += 12
            elif period and period.lower() == 'am' and hour == 12:
                hour = 0
            
            times.append(f"{hour:02d}:{minute:02d}")
        
        # Pattern for simple hour with AM/PM
        pattern_simple = r'(\d{1,2})\s*(am|pm|AM|PM)'
        matches = re.findall(pattern_simple, text, re.IGNORECASE)
        
        for hour, period in matches:
            hour = int(hour)
            minute = 0
            
            if period and period.lower() == 'pm' and hour < 12:
                hour += 12
            elif period and period.lower() == 'am' and hour == 12:
                hour = 0
            
            times.append(f"{hour:02d}:{minute:02d}")
        
        # Sort times
        times.sort()
        
        return times
    
    def _extract_duration(self, text):
        """Extract duration in minutes from text"""
        # Pattern: "for X hours"
        hour_pattern = r'for\s+(\d+)\s*(hour|hours|hr|hrs)'
        match = re.search(hour_pattern, text, re.IGNORECASE)
        if match:
            hours = int(match.group(1))
            return hours * 60
        
        # Pattern: "for X minutes"
        minute_pattern = r'for\s+(\d+)\s*(minute|minutes|min|mins)'
        match = re.search(minute_pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Pattern: "X hour(s) and Y minute(s)"
        combined_pattern = r'(\d+)\s*(hour|hours|hr|hrs)\s*and\s*(\d+)\s*(minute|minutes|min|mins)'
        match = re.search(combined_pattern, text, re.IGNORECASE)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(3))
            return hours * 60 + minutes
        
        return 60  # Default 1 hour
    
    def _calculate_end_time(self, start_time, duration_minutes):
        """Calculate end time from start time and duration"""
        try:
            # Parse start time
            start_hour, start_minute = map(int, start_time.split(':'))
            
            # Calculate end time
            total_minutes = start_hour * 60 + start_minute + duration_minutes
            end_hour = (total_minutes // 60) % 24
            end_minute = total_minutes % 60
            
            return f"{end_hour:02d}:{end_minute:02d}"
            
        except Exception as e:
            logger.error(f"Error calculating end time: {str(e)}")
            return "17:00"  # Default end time