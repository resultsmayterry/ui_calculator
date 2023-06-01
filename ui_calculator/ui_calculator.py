# -*- coding: utf-8 -*-
"""
Created on Fri Apr 24 15:09:28 2020
@author: probert2
"""

import pandas as pd
import numpy as np
import os

#hope this works...
CUR_PATH = "C:/Users/dragm/Documents/GitHub/ui_calculator/ui_calculator"
#CUR_PATH = os.path.split(os.path.abspath(__file__))[0]

def get_file(f):
    # Returns as CSV in the data folder as a pandas DataFrame.
    return pd.read_csv(os.path.join(CUR_PATH, 'data', f))

#This CSV contains the parameters needed to calculate benefits amount
state_rules = get_file('state_thresholds.csv')

#This CSV contains the parameters needed to calculate eligibility
state_eligibility = get_file('state_eligibility.csv')

def calc_weekly_schedule(df):
    '''Finds weekly benefits from wages in a given period, a rate and intercept,
    a maximum benefit amount an a minimum benefit amount.
    '''
    
    df['wba'] = (df.base_wage * df.rate) + df.intercept
    df['wba'] = df[['wba', 'maximum']].min(axis=1)
    df['wba'] = df[['wba', 'minimum']].max(axis=1)

    return df
    

def is_eligible(df):
    '''
    Look up by state, and check eligibility from a list of quarterly earnings
    in the base period,and a potential weekly benefit amount if they are found
    to be eligible
    '''
    
    #merge in eligibility rules
    df = df.merge(state_eligibility,
                  how='inner', #shouldn't matter at this point...
                  on='state'
    )
    #apply rules. uses q_concepts
    df['eligible'] = True
    
    df.loc[df.q_annual < df.absolute_base,'eligible'] = False
    df.loc[df.q_annual < df.hqw*df.q_hqw,'eligible'] = False
    df.loc[df.q_hqw < df.absolute_hqw,'eligible'] = False
    df.loc[df.q_annual < df.wba_thresh * df.wba,'eligible'] = False
    df.loc[((df.q1>0).astype(int)+(df.q2>0).astype(int)+(df.q3>0).astype(int)+(df.q4>0).astype(int)) \
        < df.num_quarters,'eligible'] = False
    df.loc[df.q_annual - df.q_hqw < df.outside_high_q,'eligible'] = False
    df.loc[df.q_2hqw-df.q_hqw < df.absolute_2nd_high,'eligible'] = False
    df.loc[df.q_2hqw < df.wba_2hqw * df.wba,'eligible'] = False
    df.loc[df.q_2hqw < df.hqw_2hqw * df.q_hqw,'eligible'] = False
    df.loc[df.q_2hqw < df.abs_2hqw,'eligible'] = False
    
    return df.eligible
    
def find_base_wage(df):
    '''
    from a dataframe containing:
        the name of a wage concept
        list of earnings in the base period
        weeks_worked
    calculate the total earnings that are used to calculate benefits in the state and add to dataframe
    '''
    
    # add q_concepts. used again in is_eligible()
    df['q_hqw'] = df[['q1','q2','q3','q4']].max(axis=1)
    df['q_2hqw'] = df[['q1','q2','q3','q4']].apply(lambda row: row.nlargest(2).values[-1],axis=1) + df.q_hqw
    df['q_ND'] = df.q_2hqw + 0.5*df[['q1','q2','q3','q4']].apply(lambda row: row.nlargest(3).values[-1],axis=1)
    df['q_2fqw'] = df.q3+df.q4
    df['q_annual'] = df.q1+df.q2+df.q3+df.q4
    df['q_week'] = df.q_annual / df.weeks_worked
    # init base wage
    df['base_wage'] = np.NaN
    # assign correct q_concept to base wage
    df.loc[df.wage_concept == 'hqw','base_wage'] = df.q_hqw
    df.loc[df.wage_concept == '2hqw','base_wage'] = df.q_2hqw
    df.loc[df.wage_concept == 'ND','base_wage'] = df.q_ND
    df.loc[df.wage_concept == '2fqw','base_wage'] = df.q_2fqw
    df.loc[df.wage_concept == 'annual_wage','base_wage'] = df.q_annual
    df.loc[df.wage_concept == 'direct_weekly','base_wage'] = df.q_week

    return df

def calc_weekly_state(df):
    '''
    From dataframe containing:
        quarterly earnings history 
        two character state index
        weeks worked numeric
    calculate the weekly benefits.
    '''

    # mark rows for later drop dupe
    df['id'] = df.index
    
    # apply rules: use all, drop base_wage<inc_thresh, drop duplicates (for when all base_wage>=inc_thresh)
    # merge in ALL rules (highest inc thresh)
    df = df.merge(state_rules,
                  on='state',
                  how='inner' #drops incorrect or unused state indices
                  )
    # add base wage
    df = find_base_wage(df)

    #drop instances where base wage does not meet inc thresh
    df=df.drop(df[df.base_wage < df.inc_thresh].index,axis=0)
    #drop dupe keeping high inc_thresh
    df.drop_duplicates(subset='id',keep='first')

    # get raw wba
    df = calc_weekly_schedule(df)

    # check eligibility, set weekly benefit amount to 0 if ineligible
    df['eligible'] = is_eligible(df)
    df.loc[df.eligible==False,'wba'] = 0
    
    return df.wba

def calc_weekly_state_quarterly(q1, q2, q3, q4, states, weeks_worked):
    '''
    This function is designed take advantage of a dataframe operations. For lists q1,
    q2, q3, q4 which give earnings histories in order for any number of workers and
    a list of states with two character index of their state, it returns a list of 
    their weekly benefit amounts (returning 0 where the worker would be monetarily
    ineligible)
    '''

    df = pd.DataFrame({'q1':q1,
                       'q2':q2,
                       'q3':q3,
                       'q4':q4,
					   'state':states,
					   'weeks_worked':weeks_worked})
    return calc_weekly_state(df)