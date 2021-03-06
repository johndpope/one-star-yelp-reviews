#!python2
import requests
import urlparse
import sys
import nltk.data
import urllib
import urllib2
import json
import pytumblr
import random
import textwrap

from lxml import html
from PIL import Image, ImageFont, ImageDraw

def main():
    # Sets proper Yelp url
    if len(sys.argv) >= 2:
        business_url_name = sys.argv[1]
    else:
        business_url_name = 'super-h-mart-niles'

    # Gets html for business
    business_page = requests.get('http://www.yelp.com/biz/' + business_url_name)
    business_tree = html.fromstring(business_page.text)

    # Gets business name and image
    business_name = business_tree.xpath('//h1[@itemprop="name"]/text()')[0].strip().encode('ascii','ignore')
    img_url = top_google_img_url(business_name.replace(' ','%20'))
    if (img_url == None):
        print "Uh-oh! No properly sized images were found :("
        return
    img_name = urlparse.urlparse(img_url).path.split('/')[-1]
    urllib.urlretrieve(img_url, 'downloaded/' + img_name)

    # Finds review count on page and retrieves the last page of reviews
    review_count = int(business_tree.xpath('//a[@data-lang="en"]/..//span[@class="count"]/text()')[0])
    offset = (review_count - 1) //40 * 40;
    page = requests.get('http://www.yelp.com/biz/' + business_url_name + '?start=' + str(offset) + '&sort_by=rating_desc')
    tree = html.fromstring(page.text)

    # Gets all one star review wrappers
    one_star_reviews = tree.xpath('//meta[@itemprop="ratingValue"][@content="1.0"]/../../../../..')
    
    if not one_star_reviews:
        print "Uh-oh! No one-star reviews found, looking at two-star reviews"
        one_star_reviews = tree.xpath('//meta[@itemprop="ratingValue"][@content="2.0"]/../../../../..')
        stars = 2
    else:
        stars = 1

    # Makes list of reviews along with their total rating and finds the funniest rated review
    highest_rating_sum = -1
    funniest_rating = -1
    review_rating_pairs = []
    for review_wrapper in one_star_reviews:
        review_text = ' '.join(review_wrapper.xpath('div//p[@itemprop="description"]/text()')).replace(u'\xa0', '')
        review_ratings = review_wrapper.xpath('*//span[@class="count"]//text()')
        funny_rating = review_wrapper.xpath('*//span[@class="i-wrap ig-wrap-common i-ufc-funny-common-wrap button-content"]/span[@class="count"]//text()')
        if not funny_rating:
            funny_rating = 0
        else:
            funny_rating = int(funny_rating[0])
        rating_sum = sum(map(int, review_ratings))
        
        review_rating_pair = [review_text, rating_sum]
        review_rating_pairs.append(review_rating_pair)
        if rating_sum > highest_rating_sum:
            highest_rated_review = review_rating_pair
            highest_rating_sum = rating_sum
            
        if funny_rating > funniest_rating:
            funniest_review = review_rating_pair
            funniest_rating = funny_rating

    # Breaks review text into sentences
    tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
    sentences = tokenizer.tokenize(funniest_review[0])
    
    # Either picks sentence randomly or prompts user to select, based on command line arguments
    if len(sys.argv) >= 3 and sys.argv[2] is 'rand':
        text = '"%s" - Yelp, %s, %s/5 stars' % (random.choice(sentences), business_name, stars)
    else:
        for sentence in enumerate(sentences):
            print sentence
        print '\n'
        selection = raw_input("Enter sentence number(s), separated by spaces or 'c' to cancel: ")
        if (selection == 'c'):
            print "Canceled, no image generated"
            return
        indexes = map(int, selection.split(' '))
        chosen = ' '.join([sentences[i] for i in indexes])
        text = '"%s" - Yelp, %s, %s/5 stars' % (chosen, business_name, stars)

    # Draws text on the image and starts posting process
    new_name = draw_text(img_name, text)
    post_picture(new_name, text)

# Finds the first Google image search result that meets the size requirements
def top_google_img_url (biz_name):
    # Uses Google API to get only photo results
    search_url = 'http://ajax.googleapis.com/ajax/services/search/images?v=1.0&q=%s&imgtype=photo' % biz_name
    conn = urllib2.urlopen(search_url)
    try:
        response = json.loads(conn.read())
    finally:
        conn.close()
        
    # Processes result JSON to find image
    images = response['responseData']['results']
    for img in images:
        if big_enough(img):
            return img['unescapedUrl']
    return None

def big_enough (img):
    return int(img['height']) >= 512 and int(img['width']) >= 512
    
# Uses PIL to overlay rectangle and text to image
def draw_text (img_name, text):
    # Draws semi-transparent black rectangle starting at 70% down the image to increase text visibility
    img = Image.open('downloaded/' + img_name)
    img.thumbnail((1000, 1000), Image.ANTIALIAS)
    img_width, img_height = img.size
    draw = ImageDraw.Draw(img, 'RGBA')
    draw.rectangle([(0, img_height * 0.7), (img_width, img_height * 0.7 + 150)], (0, 0, 0, 150))
    
    # Wraps text and finds largest text size that will fit inside the rectangle
    wrapped = textwrap.wrap(text, 70)
    font, text_width, text_height = fit_text(wrapped, img_width, 150)
    
    # Draws lines of text on the image
    text_y_pos = img_height * 0.7 + (150 - text_height) / 2
    for line in wrapped:
        line_width, line_height = font.getsize(line)
        text_x_pos = (img_width - line_width) / 2
        draw.text((text_x_pos, text_y_pos), line, (255,255,255), font)
        text_y_pos += line_height
    
    # Saves the image in the captioned/ folder
    new_name = 'capt_' + img_name
    img.save('captioned/' + new_name)
    
    return new_name
    
# Finds the largest text size possible that fits within the bounds
def fit_text (lines, width, height):
    test_size = 14
    test_font = ImageFont.truetype('Bitter-Regular.otf', test_size)
    text_width, text_height = text_size(test_font, lines)
    max_width = width * 0.8
    max_height = height * 0.8
    
    # Increments font size until it just passes fit specs
    while text_width < max_width and text_height < max_height:
        test_size += 2
        test_font = ImageFont.truetype('Bitter-Regular.otf', test_size)
        text_width, text_height = text_size(test_font, lines)
    return [test_font, text_width, text_height]

# Returns the total size of multiple lines of text in specified font
def text_size (font, lines):
    total_width = 0
    total_height = 0
    for line in lines:
        width, height = font.getsize(line)
        total_height += height + 5
        if width > total_width:
            total_width = width
    return [total_width, total_height]
    
# Posts picture on tumblr
def post_picture (img_name, caption):
    choice = raw_input("Take a look! Enter p to post, q to queue, d to draft, anything else to cancel:")
    if choice is 'p':
        state = 'published'
    elif choice is 'q':
        state = 'queue'
    elif choice is 'd':
        state = 'draft'
    else:
        return
    
    # Put your tumblr API keys here
    client = pytumblr.TumblrRestClient(
      'get yer own'
    )
    
    # Fixes caption and posts to tumblr!
    pls = caption.replace(' ','&nbsp;')
    client.create_photo('onestaryelp', state=state, tags=["yelp"], data='captioned/' + str(img_name), caption=pls)

if __name__ == '__main__':
    main()