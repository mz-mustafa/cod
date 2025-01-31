import pandas as pd
import os
from pathlib import Path

def get_keyword_type(keyword):
    """Determine the type of a keyword"""
    # Convert to lowercase for comparison
    keyword = str(keyword).lower()
    words = keyword.split()
    
    # Brand terms
    brand_terms = {
        'abbott', 'abided', 'accenture', 'albariño', 'aluminium', 'vattenfall', 
        'aspiresr', 'baldero chianti classico', 'wineandsomething', 'cambridge', 
        'carus vini', 'castillo de benizar', 'chep', 'clyde', 'novavax', 'cressive', 
        'lennox', 'defitelio', 'dh', 'elt', 'ensure', 'epidiolex', 'esl', 'essenz', 
        'gale', 'glucerna', 'gren', 'growthpoint', 'gw', 'matrix-m', 'irdeto', 'jazz', 
        'little birdie', 'livanova', 'medtronic', 'national geographic', 'nat geo', 
        'nestle', 'netfort', 'neuropace', 'ngl', 'novavax', 'nuvaxovid', 'pediasure', 
        'philippe glavier', 'protekduo', 'richard game', 'rockarchive', 'roger & didier', 
        'sativex', 'similac', 'eltngl', 'sunosi', 'tandemheart', 'vyxeos', 'will bosi', 
        'william bosi', 'wine and', 'wine club', 'wineandsomething', 'wine&earth', 'zeal'
    }
    
    # Check for brand terms
    for brand in brand_terms:
        if brand in keyword:
            return 'branded'
    
    # Other indicators
    navigational_indicators = ['archives', 'website', '.com', '.org', 'portal', 'login', 'sign in', 'database']
    commercial_indicators = ['buy', 'price', 'cost', 'purchase', 'shop', 'product', 'formula', 'subscription']
    transactional_indicators = ['how to', 'repair', 'fix', 'get', 'download', 'register', 'apply', 'book']
    
    # Check for other types
    for indicator in navigational_indicators:
        if indicator in keyword:
            return 'navigational'
            
    for indicator in commercial_indicators:
        if indicator in keyword:
            return 'commercial'
            
    for indicator in transactional_indicators:
        if indicator in keyword:
            return 'transactional'
    
    # Default type
    return 'informational'

def main():
    try:
        # Get the user's home directory
        home_dir = str(Path.home())
        
        # Construct file paths
        input_path = os.path.join(home_dir, 'refined.csv')
        output_path = os.path.join(home_dir, 'types.csv')
        
        # Read the input CSV
        print(f"Reading from: {input_path}")
        df = pd.read_csv(input_path)
        
        # Create new column with keyword types
        print("Classifying keywords...")
        df['keyword_type'] = df['keyword'].apply(get_keyword_type)
        
        # Select only the keyword and type columns
        result_df = df[['keyword', 'keyword_type']]
        
        # Write to new CSV
        print(f"Writing results to: {output_path}")
        result_df.to_csv(output_path, index=False)
        
        print("Complete! Here's a summary of the classifications:")
        print(result_df['keyword_type'].value_counts())
        
    except FileNotFoundError:
        print(f"Error: Could not find 'refined.csv' in {home_dir}")
        print("Please make sure the file is in your home directory")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()