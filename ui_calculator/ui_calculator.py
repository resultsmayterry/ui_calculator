# -*- coding: utf-8 -*-
"""
Created on Fri Apr 24 15:09:28 2020
@author: probert2
"""

import pandas as pd
import numpy as np
import os

#hope this works...
CUR_PATH = "/home/y6hwb/util/conda/ui_calculator"
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
    
    no_truncation_benefits = (df.base_wage * df.rate) + df.intercept
    
    benefits = max(min(no_truncation_benefits, df.maximum), df.minimum)
    
    return benefits
    

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
    #apply rules
    df['eligible'] = True
    
    df.loc[sum(df.base_period.str) < df.absolute_base,'eligible'] = False
    df.loc[sum(df.base_period.str) < df.hqw*max(df.base_period.str),'eligible'] = False
    df.loc[max(df.base_period.str) < df.absolute_hqw,'eligible'] = False
    df.loc[sum(df.base_period.str) < df.wba_thresh * df.wba,'eligible'] = False
    df.loc[sum([qw > 0 for qw in df.base_period.str]) < df.num_quarters,'eligible'] = False
    df.loc[sum(df.base_period.str) - max(df.base_period.str) < df.outside_high_q,'eligible'] = False
    df.loc[np.sort(df.base_period.str)[-2] < df.absolute_2nd_high,'eligible'] = False
    df.loc[sum(np.sort(df.base_period.str)[-2:]) < df.wba_2hqw * df.wba,'eligible'] = False
    df.loc[sum(np.sort(df.base_period.str)[-2:]) < df.hqw_2hqw * max(df.base_period.str),'eligible'] = False
    df.loc[sum(np.sort(df.base_period.str)[-2:]) < df.abs_2hqw,'eligible'] = False
    
    return df.eligible
    
def find_base_wage(df):
    '''
    from a dataframe containing:
        the name of a wage concept
        list of earnings in the base period
        weeks_worked
    calculate the total earnings that are used to calculate benefits in the state and add to dataframe
    '''
    
    df['base_wage']=np.NaN
    #check these
    df.loc[df.wage_concept == '2hqw','base_wage'] = sum((np.sort(df.base_period.str))[-2:])
    df.loc[df.wage_concept == 'hqw','base_wage'] = max(df.base_period.str)
    df.loc[df.wage_concept == 'annual_wage','base_wage'] = sum(df.base_period.str)
    df.loc[df.wage_concept == '2fqw','base_wage'] = sum(df.base_period.str[-2:])
    df.loc[df.wage_concept == 'ND','base_wage'] = (sum((np.sort(df.base_period.str))[-2:]) + 0.5*np.sort(df.base_period.str)[-3])
    df.loc[df.wage_concept == 'direct_weekly','base_wage'] = sum(df.base_period.str)/df.weeks_worked    

    return df

def calc_weekly_state(df):
    '''
    From dataframe containing:
        quarterly earnings history in chronological order, 
        two character state index
        weeks worked numeric
    calculate the weekly benefits.
    '''

    # create for compatbility with existing functions
    df['base_period'] = df.earnings_history.str[-5:-1]
    # merge in first try rules (highest inc thresh)
    df = df.merge(state_rules.drop_duplicates(subset='state',keep='first'),
                  on='state',
                  how='inner' #drops incorrect or unused state indices
                  )
    #add base wage
    df = find_base_wage(df)
    
    #update rules when base wage does not meet inc thresh (isolate, drop, modify, append)
    df_update = df.loc[df.base_wage < df.inc_thresh,['earnings_history','state','weeks_worked','base_period']]
    df=df.drop(df[df.base_wage < df.inc_thresh])
    
    df_update=df_update.merge(state_rules.loc[state_rules.duplicated(subset='state',keep='first')],
                              on='state',
                              how='inner', #drops incorrect or unused state indices
                              )       
    #find the basewage on the alternate concept
    df_update = find_base_wage(df_update)

    df = pd.concat([df,df_update],axis=0)

    df['wba'] = calc_weekly_schedule(df)
    # check eligibility, set weekly benefit amount to 0 if ineligible
    df.eligible = is_eligible(df)
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

    earnings_history = pd.Series([q1, q2, q3, q4, 0]) #UPDATE
    df = pd.DataFrame({'earnings_history':earnings_history,
					   'state':states,
					   'weeks_worked':weeks_worked})
    
    return calc_weekly_state(df)
