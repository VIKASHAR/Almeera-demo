import sqlite3
import pandas as pd
import json
import os
import sys

def compute_and_save_affinity(db_path="db/mvp_demo.db", min_support=0.05, min_confidence=0.3):
    """
    Computes association rules from the purchase_history table in the SQLite database.
    Attempts to use mlxtend (Apriori), with a clean, native Python fallback if mlxtend is not installed.
    Saves results to the affinity table.
    """
    print(f"Connecting to database at: {db_path}")
    if not os.path.exists(db_path):
        # If relative path fails, try parent path or create directories
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Read transactions
    try:
        query = "SELECT transaction_id, sku FROM purchase_history"
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"Error reading purchase_history: {e}. Seeding might not be complete yet.")
        conn.close()
        return

    if df.empty:
        print("No transactions found in purchase_history. Skipping affinity computation.")
        conn.close()
        return

    print(f"Loaded {len(df)} transaction items. Computing affinity...")
    
    # Try using mlxtend
    success = False
    rules = []
    
    try:
        from mlxtend.frequent_patterns import apriori, association_rules
        from mlxtend.preprocessing import TransactionEncoder
        
        # Group by transaction_id to get list of lists
        transactions = df.groupby('transaction_id')['sku'].apply(list).tolist()
        
        te = TransactionEncoder()
        te_ary = te.fit(transactions).transform(transactions)
        df_encoded = pd.DataFrame(te_ary, columns=te.columns_)
        
        frequent_itemsets = apriori(df_encoded, min_support=min_support, use_colnames=True)
        
        if not frequent_itemsets.empty:
            rules_df = association_rules(frequent_itemsets, metric="confidence", min_threshold=min_confidence)
            for _, row in rules_df.iterrows():
                # Extract antecedents and consequents
                for ant in row['antecedents']:
                    for cons in row['consequents']:
                        rules.append((ant, cons, float(row['confidence'])))
            success = True
            print("Successfully computed affinity using mlxtend (Apriori).")
    except ImportError:
        print("mlxtend not installed. Falling back to native Python association mining.")
    except Exception as e:
        print(f"Error in mlxtend processing: {e}. Falling back to native Python association mining.")
        
    if not success:
        # Fallback association mining:
        # We manually compute support and confidence for pairs
        # Transactions list of lists
        transactions = df.groupby('transaction_id')['sku'].apply(set).tolist()
        N = len(transactions)
        
        if N == 0:
            conn.close()
            return
            
        # Count individual frequencies (support counts)
        item_counts = {}
        pair_counts = {}
        
        for tx in transactions:
            for item in tx:
                item_counts[item] = item_counts.get(item, 0) + 1
            tx_list = list(tx)
            for i in range(len(tx_list)):
                for j in range(i + 1, len(tx_list)):
                    item_a, item_b = tx_list[i], tx_list[j]
                    # order them to count co-occurrence
                    pair = (item_a, item_b) if item_a < item_b else (item_b, item_a)
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1
                    
        # Now find rules A -> B and B -> A
        for pair, count in pair_counts.items():
            item_a, item_b = pair
            support = count / N
            if support >= min_support:
                # Confidence A -> B = support(A, B) / support(A)
                conf_a_to_b = count / item_counts[item_a]
                if conf_a_to_b >= min_confidence:
                    rules.append((item_a, item_b, conf_a_to_b))
                
                # Confidence B -> A = support(A, B) / support(B)
                conf_b_to_a = count / item_counts[item_b]
                if conf_b_to_a >= min_confidence:
                    rules.append((item_b, item_a, conf_b_to_a))
        print(f"Successfully computed affinity using native fallback algorithm. Found {len(rules)} rules.")

    # Save to affinity table
    try:
        # Clear existing affinity records
        cursor.execute("DELETE FROM affinity")
        
        # Insert rules
        cursor.executemany(
            "INSERT OR REPLACE INTO affinity (sku_a, sku_b, confidence_score) VALUES (?, ?, ?)",
            rules
        )
        conn.commit()
        print(f"Inserted/Replaced {len(rules)} association pairs in affinity table.")
    except Exception as e:
        print(f"Failed to save affinity: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    db = "db/mvp_demo.db"
    if len(sys.argv) > 1:
        db = sys.argv[1]
    compute_and_save_affinity(db)
