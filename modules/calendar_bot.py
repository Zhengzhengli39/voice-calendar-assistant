"""
Calendar automation module using Playwright
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class CalendarBot:
    def __init__(self, auth_state_path, manual_login=False):
        """
        Initialize Calendar Bot
        
        Args:
            auth_state_path: Path to authentication state file
            manual_login: Whether to show browser for manual login
        """
        self.auth_state_path = Path(auth_state_path)
        self.manual_login = manual_login
        self.browser = None
        self.context = None
        self.page = None
        
        # Create storage directory if it doesn't exist
        self.auth_state_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize in background thread
        asyncio.create_task(self._initialize_async())
    
    async def _initialize_async(self):
        """Initialize Playwright browser asynchronously"""
        try:
            self.playwright = await async_playwright().start()
            
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
            
            if self.auth_state_path.exists() and not self.manual_login:
                # Load existing authentication state
                logger.info(f"Loading authentication state from {self.auth_state_path}")
                
                self.browser = await self.playwright.chromium.launch(
                    headless=False,  # Show browser for debugging
                    args=browser_args
                )
                
                self.context = await self.browser.new_context(
                    storage_state=self.auth_state_path,
                    viewport={'width': 1280, 'height': 720}
                )
            else:
                # Start fresh browser session
                logger.info("Starting new browser session")
                
                self.browser = await self.playwright.chromium.launch(
                    headless=False,  # Always show for manual login
                    args=browser_args
                )
                
                self.context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 720}
                )
            
            self.page = await self.context.new_page()
            
            # Navigate to Google Calendar
            await self._navigate_to_calendar()
            
            # Save auth state if this was a manual login
            if self.manual_login and self.auth_state_path:
                await self._save_auth_state()
            
            logger.info("Calendar bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize calendar bot: {str(e)}")
            raise
    
    async def _navigate_to_calendar(self):
        """Navigate to Google Calendar"""
        try:
            await self.page.goto('https://calendar.google.com')
            
            # Wait for calendar to load
            await self.page.wait_for_selector('text="Google Calendar"', timeout=10000)
            
            # Check if we're on the calendar page
            current_url = self.page.url
            if 'calendar.google.com' not in current_url:
                logger.warning("Not on calendar page, current URL: {current_url}")
            
            logger.info("Successfully navigated to Google Calendar")
            
        except Exception as e:
            logger.error(f"Error navigating to calendar: {str(e)}")
            # Try to continue anyway
    
    async def _save_auth_state(self):
        """Save authentication state"""
        try:
            await self.context.storage_state(path=self.auth_state_path)
            logger.info(f"Authentication state saved to {self.auth_state_path}")
        except Exception as e:
            logger.error(f"Error saving auth state: {str(e)}")
    
    def add_calendar_event(self, event_data):
        """
        Add event to Google Calendar
        
        Args:
            event_data: Dictionary containing event details
            
        Returns:
            dict: Result with success status and additional info
        """
        try:
            # Run async function in sync context
            return asyncio.run(self._add_calendar_event_async(event_data))
        except Exception as e:
            logger.error(f"Error adding calendar event: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _add_calendar_event_async(self, event_data):
        """Async implementation of add_calendar_event"""
        try:
            logger.info(f"Adding event: {event_data}")
            
            # Ensure page is ready
            if not self.page:
                await self._navigate_to_calendar()
            
            # Click create button
            create_button = self.page.locator('div[role="button"]:has-text("Create")').first
            await create_button.click(timeout=5000)
            
            # Wait for event dialog
            await self.page.wait_for_selector('div[role="dialog"]', timeout=5000)
            
            # Fill event title
            title_input = self.page.locator('input[aria-label="Add title"]').first
            await title_input.fill(event_data['title'])
            
            # Set date
            await self._set_event_date(event_data['date'])
            
            # Set start time
            await self._set_event_time('start', event_data['start_time'])
            
            # Set end time
            await self._set_event_time('end', event_data['end_time'])
            
            # Check for conflicts
            conflict = await self._check_conflict(event_data)
            if conflict:
                return {
                    'success': False,
                    'conflict': True,
                    'error': 'Time slot is already occupied'
                }
            
            # Save event
            save_button = self.page.locator('button:has-text("Save")').first
            await save_button.click()
            
            # Wait for save to complete
            await asyncio.sleep(2)
            
            logger.info(f"Event '{event_data['title']}' added successfully")
            
            return {
                'success': True,
                'event_title': event_data['title'],
                'date': event_data['date'],
                'time': f"{event_data['start_time']} - {event_data['end_time']}"
            }
            
        except Exception as e:
            logger.error(f"Error in calendar event creation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _set_event_date(self, date_str):
        """Set event date in calendar dialog"""
        try:
            # Click date field
            date_field = self.page.locator('input[aria-label*="Date"]').first
            await date_field.click()
            
            # Clear and enter date
            await date_field.fill(date_str)
            await self.page.keyboard.press('Enter')
            
            await asyncio.sleep(1)  # Wait for date to apply
            
        except Exception as e:
            logger.warning(f"Error setting date: {str(e)}")
            # Try alternative approach
            await self._set_date_alternative(date_str)
    
    async def _set_date_alternative(self, date_str):
        """Alternative method to set date"""
        try:
            # Try using the date picker
            date_picker = self.page.locator('div[role="dialog"] input[type="date"]').first
            if await date_picker.is_visible():
                await date_picker.fill(date_str)
            
        except Exception as e:
            logger.error(f"Alternative date setting also failed: {str(e)}")
    
    async def _set_event_time(self, time_type, time_str):
        """Set event time (start or end)"""
        try:
            # Locate time field based on type
            if time_type == 'start':
                time_field = self.page.locator('input[aria-label*="Start time"]').first
            else:
                time_field = self.page.locator('input[aria-label*="End time"]').first
            
            await time_field.click()
            await time_field.fill(time_str)
            await self.page.keyboard.press('Enter')
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Error setting {time_type} time: {str(e)}")
    
    async def _check_conflict(self, event_data):
        """Check if there's a scheduling conflict"""
        try:
            # This is a simplified check - in production, you'd want to
            # actually check the calendar for existing events
            
            # For now, we'll check if the "Busy" indicator appears
            busy_indicator = self.page.locator('text="Busy"').first
            if await busy_indicator.is_visible(timeout=2000):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking conflict: {str(e)}")
            return False
    
    async def close(self):
        """Close browser and cleanup"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("Calendar bot closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing calendar bot: {str(e)}")