
__author__ = "glebourgeois@me.com"
__version__ = "0.1a"
__date__ ="2011-03-05"

import xlrd3
import csv
import string # FIXME: is this useful ?
import sys

class pyParserXLS:
  """
  Versions of Excel supported: 2003, 2002, XP, 2000, 97, 95
  XLRD3 Documentation : http://packages.python.org/xlrd3/
  """

  def __init__(self):
    self.filename = None
    self.book = None

  def extract_meta(self, filename):
    self.filename = filename
    self.book = xlrd3.open_workbook(filename)

  def show_cells_content(self, sheet):

    for row in range( 0, sheet.nrows ):
      for col in range( 0, sheet.ncols ):
        print( "%d;%d : %s" % ( row, col, sheet.cell_value(row, col) ) )

  def find_titles_row(self, sheet):
    """
    Looks for the first row which seems to contain columns titles,
    and indicates where the data "starts".
    """
    # amount of cols which must be strings
    min_str_cols = int( round(0.8 * sheet.ncols) )
    print( "We look for at least %d string cols" % min_str_cols )

    for row in range( 0, sheet.nrows ):
      count = 0
      detected = False # has a str already been detected ?
      
      for col in range( 0, sheet.ncols ):
        cell = sheet.cell(row, col)
        if cell.ctype == xlrd3.XL_CELL_TEXT:
          #print( cell.value )
          detected = True
          count += 1

          if( count >= min_str_cols ):
            print( "Found row %d " % row )
            self._print_row( sheet, row )
            return row

        else:
          # no continuity in strings for this row, let's try next one
          if detected is True:
            break

  def _print_row(self, sheet, row):
    line = ""
    for  col in range( 0, sheet.ncols ):
      line += "[%s]" % sheet.cell_value(row, col)

    print( line )

  def __str__(self):
    s = "\n"
    s += "-- %s --\n" % self.filename
    
    for i in range ( 0, self.book.nsheets ):
      sheet = self.book.sheet_by_index( i )
      
      s += "Sheet %s\n" % sheet.name
      s += "\t%d rows\n" % sheet.nrows
      s += "\t%d columns\n" % sheet.ncols
      s += "\n"

    return s
  
  def xls2csv(self, excel_filename,csv_filename):
      try:
          book = xlrd3.open_workbook(excel_filename)
          print("The number of worksheets: %d" % book.nsheets)
          sheet_name = book.sheet_names()[0].split(' ')[0] #The first sheet
          sh = book.sheet_by_index(0)
          print("Sheet name:", sh.name, " | Number of rows:", sh.nrows, " | Number of columns:", sh.ncols)
          csv_file = open(csv_filename,'w') 
          w = csv.writer(csv_file, csv.excel)
          for row in range(sh.nrows):
              cell_types = sh.row_types(row)
              this_row = []
              for col in range(sh.ncols):
                  if cell_types[col] == xlrd3.XL_CELL_DATE:
                      cell_val = datetime.datetime(*xlrd3.xldate_as_tuple(sh.cell_value(row,col), book.datemode))
                  else:
                     cell_val =  str(sh.cell_value(row,col)).encode('utf8')
                  this_row.append(cell_val)
              if row == 0 or (row > 0 and this_row[1].isdigit()):
                  w.writerow(this_row)
          print("%s has been created" % csv_filename)
      except IOError:
          print("IOError: Please ensure %s exists" % excel_filename) 

if __name__ == "__main__":
    p = pyParserXLS()
    p.extract_meta( sys.argv[1] )
    #p.show_cells_content(p.book.sheet_by_index( 0 ) ) # show first sheet content
    p.find_titles_row( p.book.sheet_by_index( 0 ) ) # finds cols titles row

    print( p )

