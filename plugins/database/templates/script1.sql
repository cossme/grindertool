insert into test( id, col1, col2, col3) values ( seq_test.nextval, ?, ?, ?)@@${value1},${value2},${value3}
select seq_test.currval from dual@@id 
update test set col3=col3||' ++' where id = ?@@${id}
commit