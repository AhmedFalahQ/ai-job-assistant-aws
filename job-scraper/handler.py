"""
Job Scraper Worker Lambda (Container)
Invoked asynchronously by job-scraper-start.
Does the actual Playwright scraping and stores result in DynamoDB.
No API Gateway timeout concern — runs as long as needed.
"""

import json
import logging
import re
from datetime import datetime, timezone

import boto3
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb   = boto3.resource('dynamodb')
TABLE_NAME = 'scrape-jobs'

CHROMIUM_ARGS = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--single-process',
    '--no-zygote',
    '--disable-extensions',
    '--disable-background-networking',
    '--disable-default-apps',
    '--mute-audio',
    '--no-first-run',
]


def lambda_handler(event, context):
    """
    Input: { "job_id": "uuid", "url": "linkedin url" }
    Stores result in DynamoDB under job_id.
    """
    job_id = event.get('job_id')
    url    = event.get('url', '').strip()

    logger.info(f"Worker started — job_id: {job_id}, url: {url}")

    table = dynamodb.Table(TABLE_NAME)

    try:
        # Update status to processing
        table.update_item(
            Key={ 'job_id': job_id },
            UpdateExpression='SET #s = :s',
            ExpressionAttributeNames={ '#s': 'status' },
            ExpressionAttributeValues={ ':s': 'processing' }
        )

        # Do the scraping
        result = scrape_job(url)

        if not result.get('description'):
            raise ValueError("Could not extract job description from this URL")

        logger.info(f"Scraping successful — title: {result.get('title')}")

        # Store result in DynamoDB
        table.update_item(
            Key={ 'job_id': job_id },
            UpdateExpression='SET #s = :s, #r = :r, completed_at = :t',
            ExpressionAttributeNames={
                '#s': 'status',
                '#r': 'result'
            },
            ExpressionAttributeValues={
                ':s': 'done',
                ':r': json.dumps(result),
                ':t': datetime.now(timezone.utc).isoformat()
            }
        )

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Worker failed: {str(e)}", exc_info=True)

        # Store error in DynamoDB so frontend can show it
        try:
            table.update_item(
                Key={ 'job_id': job_id },
                UpdateExpression='SET #s = :s, error_msg = :e',
                ExpressionAttributeNames={ '#s': 'status' },
                ExpressionAttributeValues={
                    ':s': 'error',
                    ':e': str(e)
                }
            )
        except Exception as db_err:
            logger.error(f"Failed to store error in DynamoDB: {str(db_err)}")


def scrape_job(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=CHROMIUM_ARGS
        )

        context = browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            viewport={ 'width': 1280, 'height': 800 },
            locale='en-US'
        )

        page = context.new_page()

        logger.info("Browser launched — navigating to URL")

        page.goto(url, wait_until='domcontentloaded', timeout=60000)

        try:
            page.wait_for_load_state('networkidle', timeout=15000)
        except Exception:
            logger.warning("networkidle timeout — continuing")

        # Click see more if present
        try:
            btn = page.query_selector('button.show-more-less-html__button')
            if btn:
                btn.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        html = page.content()
        browser.close()

    logger.info(f"Page loaded — {len(html)} chars")
    return parse_job_html(html)


def parse_job_html(html: str) -> dict:
    soup = BeautifulSoup(html, 'lxml')

    result = {
        'title':       None,
        'company':     None,
        'location':    None,
        'description': None
    }

    # Strategy 1 — JSON-LD
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = next((d for d in data if d.get('@type') == 'JobPosting'), None)
            if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                result['title']   = data.get('title')
                hiring_org        = data.get('hiringOrganization', {})
                result['company'] = hiring_org.get('name')
                job_loc           = data.get('jobLocation', {})
                if isinstance(job_loc, list): job_loc = job_loc[0]
                if isinstance(job_loc, dict):
                    result['location'] = job_loc.get('address', {}).get('addressLocality')
                result['description'] = clean_description(data.get('description', ''))
                logger.info("Extracted via JSON-LD")
                return result
        except Exception:
            continue

    # Strategy 2 — HTML selectors
    logger.info("Falling back to HTML selectors")

    for sel in ['.show-more-less-html__markup','.jobs-description-content__text',
                '.jobs-box__html-content','.description__text']:
        el = soup.select_one(sel)
        if el:
            result['description'] = clean_description(el.get_text(separator='\n', strip=True))
            break

    for sel in ['h1.top-card-layout__title','h1.t-24',
                '.job-details-jobs-unified-top-card__job-title h1','h1']:
        el = soup.select_one(sel)
        if el: result['title'] = el.get_text(strip=True); break

    for sel in ['.topcard__org-name-link',
                '.job-details-jobs-unified-top-card__company-name',
                '.jobs-unified-top-card__company-name']:
        el = soup.select_one(sel)
        if el: result['company'] = el.get_text(strip=True); break

    for sel in ['.topcard__flavor--bullet',
                '.job-details-jobs-unified-top-card__primary-description-container']:
        el = soup.select_one(sel)
        if el: result['location'] = el.get_text(strip=True); break

    return result


def clean_description(text: str) -> str:
    if not text: return ''

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '\n', text)

    # Smart quotes → straight quotes
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')

    # Em/en dashes → regular dash
    text = text.replace('\u2013', '-').replace('\u2014', '-')

    # Bullet symbols → dash
    text = text.replace('\u2022', '-').replace('\u2023', '-')

    # Remove zero-width characters
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)

    # Normalize newlines
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Clean lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Remove duplicates
    dedup = []
    for line in lines:
        if not dedup or line != dedup[-1]:
            dedup.append(line)

    return '\n'.join(dedup)